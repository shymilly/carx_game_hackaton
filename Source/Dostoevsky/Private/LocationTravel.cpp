#include "LocationTravel.h"
#include "ActOne.h"
#include "PrologueTimeOfDay.h"
#include "ExplorationHUD.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerStart.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{

// Authoring markers specify capsule-center XY and view direction. Grounding is the only adjustment.
bool SafeArrival(APlayerController* Player, const AActor* Marker, FVector& Center, FRotator& Facing)
{
    const ACharacter* Character = Player ? Cast<ACharacter>(Player->GetPawn()) : nullptr;
    const UCapsuleComponent* Capsule = Character ? Character->GetCapsuleComponent() : nullptr;
    UWorld* World = Player ? Player->GetWorld() : nullptr;
    if (!Marker || !Capsule || !World) return false;
    const FVector Authored = Marker->GetActorLocation();
    if (Authored.ContainsNaN()) return false;
    const float Half = Capsule->GetScaledCapsuleHalfHeight();
    const float Radius = Capsule->GetScaledCapsuleRadius();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(DoorArrival), false, Character);
    Query.AddIgnoredActor(Marker);
    FHitResult Floor;
    if (!World->LineTraceSingleByChannel(Floor,Authored+FVector(0,0,20),
        Authored-FVector(0,0,2*Half+60),ECC_Pawn,Query) || Floor.bStartPenetrating ||
        Floor.ImpactNormal.Z < Character->GetCharacterMovement()->GetWalkableFloorZ()) return false;
    Center = FVector(Authored.X,Authored.Y,Floor.ImpactPoint.Z+Half+3.f);
    // A marker on another storey must be corrected by its author, not silently moved through floors.
    if (FMath::Abs(Center.Z-Authored.Z) > Half+45.f) return false;
    const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
    if (World->OverlapBlockingTestByChannel(Center,FQuat::Identity,Capsule->GetCollisionObjectType(),
        FCollisionShape::MakeCapsule(Radius,Half),Query,Responses)) return false;
    Facing = Marker->GetActorRotation();
    Facing.Roll = 0;
    Facing.Pitch = FMath::Clamp(FRotator::NormalizeAxis(Facing.Pitch),-70.f,70.f);
    return true;
}
bool PutAtArrival(APlayerController* Player,const AActor* Marker,FVector& Result)
{
    FRotator Facing;
    if (!SafeArrival(Player,Marker,Result,Facing)) return false;
    ACharacter* Character=CastChecked<ACharacter>(Player->GetPawn());
    Character->GetCharacterMovement()->StopMovementImmediately();
    // Collision was tested above: disable TeleportTo's FindTeleportSpot offset so the threshold is exact.
    if (!Character->TeleportTo(Result,FRotator(0,Facing.Yaw,0),false,true)) return false;
    Character->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    Player->SetControlRotation(Facing);
    return true;
}

void SetNumber(UObject* Object,FName Name,double Value)
{
    if (FNumericProperty* P=FindFProperty<FNumericProperty>(Object->GetClass(),Name))
    {
        void* Address=P->ContainerPtrToValuePtr<void>(Object);
        if (P->IsFloatingPoint()) P->SetFloatingPointPropertyValue(Address,Value);
        else P->SetIntPropertyValue(Address,static_cast<int64>(Value));
    }
}
double Number(UObject* Object,FName Name,double Default)
{
    const FNumericProperty* P=FindFProperty<FNumericProperty>(Object->GetClass(),Name);
    if (!P) return Default;
    const void* Address=P->ContainerPtrToValuePtr<void>(Object);
    return P->IsFloatingPoint() ? P->GetFloatingPointPropertyValue(Address) : P->GetSignedIntPropertyValue(Address);
}
void SetFlag(UObject* Object,FName Name,bool Value)
{
    if (FBoolProperty* P=FindFProperty<FBoolProperty>(Object->GetClass(),Name)) P->SetPropertyValue_InContainer(Object,Value);
}
}
void ULocationTravelSubsystem::Capture(AHUD* HUD)
{
    if (!HUD) return;
    bHasSnapshot=true;
    for (TFieldIterator<FBoolProperty> It(HUD->GetClass());It;++It)
        if (It->GetName().EndsWith(TEXT("Found"))) Found.Add(It->GetFName(),It->GetPropertyValue_InContainer(HUD));
    Stamina=Number(HUD,TEXT("Stamina"),100);
    if (const FBoolProperty* P=FindFProperty<FBoolProperty>(HUD->GetClass(),TEXT("Exhausted"))) bExhausted=P->GetPropertyValue_InContainer(HUD);
    if (UGameplayStatics::GetCurrentLevelName(HUD,true)==TEXT("L_DimaApartmentInterior"))
        if (const UDimaApartmentStoryComponent* Story=HUD->FindComponentByClass<UDimaApartmentStoryComponent>()) ApartmentProgress=Story->GetTravelProgress();
    if (const APrologueTimeOfDay* Time=Cast<APrologueTimeOfDay>(UGameplayStatics::GetActorOfClass(HUD,APrologueTimeOfDay::StaticClass())))
        ClockHours=Time->GetWorldHours();
    if (const UExplorationHUDComponent* Tutorial=HUD->FindComponentByClass<UExplorationHUDComponent>()) TutorialMask=Tutorial->GetTravelMask();
}
bool ULocationTravelSubsystem::IsArrivalSafe(APlayerController* Player,FName Tag)
{
    if (!Player || Tag.IsNone()) return false;
    TArray<AActor*> Starts;
    UGameplayStatics::GetAllActorsWithTag(Player,Tag,Starts);
    FVector Position;
    FRotator Facing;
    return Starts.Num()==1 && SafeArrival(Player,Starts[0],Position,Facing);
}
bool ULocationTravelSubsystem::ApplyArrival(UWorld* World,bool bAllowFallback)
{
    if (!World) return false;
    if (ArrivalTag.IsNone()) return true;
    APlayerController* Player=UGameplayStatics::GetPlayerController(World,0);
    if (!Player || !Player->GetPawn()) return false;
    TArray<AActor*> Starts;
    UGameplayStatics::GetAllActorsWithTag(World,ArrivalTag,Starts);
    if (Starts.Num()==1 && PutAtArrival(Player,Starts[0],LastArrivalLocation))
    {
        UE_LOG(LogTemp,Log,TEXT("LOCATION_ARRIVAL_OK %s at %s yaw=%.1f"),*ArrivalTag.ToString(),
            *LastArrivalLocation.ToCompactString(),Player->GetControlRotation().Yaw);
        bLastArrivalExact=true;
        ArrivalTag=NAME_None;
        return true;
    }
    if (!bAllowFallback) return false;
    // A missing/blocked marker must never strand the player below the map. Use an authored PlayerStart.
    TArray<AActor*> Fallbacks;
    UGameplayStatics::GetAllActorsOfClass(World,APlayerStart::StaticClass(),Fallbacks);
    for (AActor* Start:Fallbacks) if (PutAtArrival(Player,Start,LastArrivalLocation))
    {
        UE_LOG(LogTemp,Warning,TEXT("LOCATION_ARRIVAL_FALLBACK: %s is missing, duplicated or obstructed; using %s"),
            *ArrivalTag.ToString(),*Start->GetName());
        bLastArrivalExact=false;
        ArrivalTag=NAME_None;
        return true;
    }
    UE_LOG(LogTemp,Error,TEXT("LOCATION_ARRIVAL_FAILED: no safe marker or PlayerStart for %s"),*ArrivalTag.ToString());
    bLastArrivalExact=false;
    return false;
}
bool ULocationTravelSubsystem::Restore(AHUD* HUD)
{
    if (!HUD) return false;
    const FString Level=UGameplayStatics::GetCurrentLevelName(HUD,true);
    const UActOneSubsystem* Act=UActOneSubsystem::Find(HUD);
    if (Level!=TEXT("L_DimaApartmentInterior") && Level!=TEXT("L_NeptuneStreet") && Level!=TEXT("L_PolicePrecinct") &&
        !(Act && Act->IsActive())) return false;
    if (Level==TEXT("L_DimaApartmentInterior") && !bHasSnapshot) return false;
    for (const auto& Entry:Found) SetFlag(HUD,Entry.Key,Entry.Value);
    SetNumber(HUD,TEXT("State"),0);
    SetNumber(HUD,TEXT("Stamina"),Stamina);
    SetFlag(HUD,TEXT("Exhausted"),bExhausted);
    SetFlag(HUD,TEXT("AtDimas"),true);
    APlayerController* Player=HUD->GetOwningPlayerController();
    if (Player && Player->GetPawn()) Player->SetViewTarget(Player->GetPawn());
    UExplorationHUDComponent* Tutorial=HUD->FindComponentByClass<UExplorationHUDComponent>();
    if (!Tutorial)
    {
        Tutorial=NewObject<UExplorationHUDComponent>(HUD);
        HUD->AddInstanceComponent(Tutorial);
        Tutorial->RegisterComponent();
    }
    Tutorial->SetTravelMask(TutorialMask);
    ApplyArrival(HUD->GetWorld());
    return true;
}
void ULocationTravelSubsystem::ResetSession()
{
    if (UGameInstance* GI=GetGameInstance()) GI->GetSubsystem<UActOneSubsystem>()->Reset();
    bHasSnapshot=false;
    bLastArrivalExact=true;
    LastArrivalLocation=FVector::ZeroVector;
    ApartmentProgress=FDimaApartmentProgress();
    ClockHours=18;
    ArrivalTag=NAME_None;
    Found.Reset();
    Stamina=100;
    bExhausted=false;
    TutorialMask=0;
    RailServiceEpoch=-1;
}

double ULocationTravelSubsystem::GetRailServiceSeconds()
{
    const double Now=FPlatformTime::Seconds();
    if (RailServiceEpoch<0) RailServiceEpoch=Now;
    return Now-RailServiceEpoch;
}
bool ULocationTravelLibrary::RestoreLocation(AHUD* HUD)
{
    return HUD && HUD->GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->Restore(HUD);
}
void ULocationTravelLibrary::ResetSession(AHUD* HUD)
{
    if (HUD) HUD->GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->ResetSession();
}

bool ULocationTravelLibrary::IsArrivalPointSafe(APlayerController* Player,FName Tag)
{
    return ULocationTravelSubsystem::IsArrivalSafe(Player,Tag);
}
bool ULocationTravelLibrary::WasLastArrivalExact(APlayerController* Player)
{
    return Player && Player->GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->bLastArrivalExact;
}
