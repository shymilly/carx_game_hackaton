#include "BrightonEnvironment.h"

#include "ActOne.h"
#include "ActOneScene.h"
#include "CityCharacter.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/SpotLight.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInterface.h"
#include "PrologueTimeOfDay.h"

UBrightonEnvironmentComponent::UBrightonEnvironmentComponent()
{
    PrimaryComponentTick.bCanEverTick=true;
    PrimaryComponentTick.TickInterval=.025f;
}

void UBrightonEnvironmentComponent::BeginPlay()
{
    Super::BeginPlay();
    Director=Cast<AActOneDirector>(GetOwner());
    Data=LoadObject<UBrightonEnvironmentData>(nullptr,TEXT("/Game/Prologue/Brighton/DA_Environment.DA_Environment"));
    for (TActorIterator<ASpotLight> Light(GetWorld());Light;++Light)
        if (Light->ActorHasTag(TEXT("WindowProjection"))) WindowLights.Add(*Light);
}

void UBrightonEnvironmentComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Delta,Type,Tick);
    if (!Director.IsValid() || !Data) return;
    APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    ACharacter* Character=Player ? Cast<ACharacter>(Player->GetPawn()) : nullptr;
    if (!Character) return;
    UpdatePlayerAppearance(Character);
    UpdateFootsteps(Character);
    const UActOneSubsystem* Story=UActOneSubsystem::Find(this);
    const bool bRain=Director->IsRaining();
    const bool bRainOutside=bRain || (Story && Story->GetPhase()>=EActOnePhase::MeetIvan);
    if (!bWeatherInitialized)
    {
        // Streets stay damp when loading another map during the scripted storm.
        Wetness=Story && Story->GetPhase()>=EActOnePhase::MeetIvan ? .8f : 0.f;
        bWeatherInitialized=true;
    }
    Wetness=FMath::FInterpConstantTo(Wetness,bRainOutside ? 1.f : 0.f,Delta,bRainOutside ? .16f : .025f);
    if (Data->WeatherParameters)
        UKismetMaterialLibrary::SetScalarParameterValue(this,Data->WeatherParameters,TEXT("Wetness"),Wetness);
    LightTimer-=Delta;
    if (LightTimer<=0)
    {
        LightTimer=.25f;
        UpdateWindowLights(Character->GetActorLocation());
    }
}

void UBrightonEnvironmentComponent::UpdatePlayerAppearance(ACharacter* Character)
{
    const UCityCharacterProfile* Appearance=Data->PlayerAppearance;
    if (!Appearance || !Appearance->Mesh) return;
    USkeletalMeshComponent* Visual=PlayerMesh.Get();
    if (!Visual || Visual->GetOwner()!=Character)
    {
        TInlineComponentArray<USkeletalMeshComponent*> Existing(Character);
        bool bTemplateCharacter=false;
        for (USkeletalMeshComponent* Original:Existing)
            if (Original->GetSkeletalMeshAsset() && Original->GetSkeletalMeshAsset()->GetFName()==TEXT("SKM_Manny_Simple"))
            {
                Original->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
                Original->SetVisibility(false);
                Original->SetCastShadow(false);
                bTemplateCharacter=true;
            }
        if (!bTemplateCharacter) return;
        if (UCameraComponent* Eyes=Character->FindComponentByClass<UCameraComponent>())
        {
            Eyes->AttachToComponent(Character->GetCapsuleComponent(),FAttachmentTransformRules::SnapToTargetNotIncludingScale);
            Eyes->SetRelativeLocation(FVector(8,0,Character->BaseEyeHeight));
            Eyes->bUsePawnControlRotation=true;
        }
        Visual=NewObject<USkeletalMeshComponent>(Character,TEXT("DimaStreetClothes"));
        Visual->SetupAttachment(Character->GetCapsuleComponent());
        Appearance->Configure(*Visual);
        Visual->SetRelativeLocation(FVector(-24,0,Appearance->FeetOffset-Character->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()));
        Visual->RegisterComponent();
        PlayerMesh=Visual;
        PlayerMotion=NAME_None;
    }
    const APlayerController* Viewer=Cast<APlayerController>(Character->GetController());
    const bool bFirstPerson=Viewer && Viewer->GetViewTarget()==Character;
    static const FName HeadBone(TEXT("Head"));
    if (Visual->IsBoneHiddenByName(HeadBone)!=bFirstPerson)
    {
        if (bFirstPerson) Visual->HideBoneByName(HeadBone,PBO_None);
        else Visual->UnHideBoneByName(HeadBone);
    }
    const UCharacterMovementComponent& Movement=*Character->GetCharacterMovement();
    const float Speed=Character->GetVelocity().Size2D();
    const bool bRun=Speed>(PlayerMotion==TEXT("Run") ? 415.f : 450.f);
    const bool bWalk=Speed>(PlayerMotion==TEXT("Walk") ? 28.f : 42.f);
    const FName Next=Movement.IsFalling() ? TEXT("Jump") : bRun ? TEXT("Run") : bWalk ? TEXT("Walk") : TEXT("Idle");
    if (PlayerMotion!=Next)
    {
        PlayerMotion=Next;
        Appearance->Play(*Visual,Next,Next!=TEXT("Jump"));
    }
    if (bWalk && !Movement.IsFalling())
    {
        const float Rate=FMath::Clamp(Speed/(bRun ? 530.f : 275.f),.60f,1.55f);
        const bool bBackwards=FVector::DotProduct(Character->GetVelocity().GetSafeNormal2D(),Character->GetActorForwardVector())<-.55f;
        Visual->SetPlayRate(bBackwards ? -Rate : Rate);
    }
}

void UBrightonEnvironmentComponent::UpdateFootsteps(ACharacter* Character)
{
    const FVector Position=Character->GetActorLocation();
    const bool bGrounded=Character->GetCharacterMovement()->IsMovingOnGround();
    const float Distance=FVector::Dist2D(Position,PreviousPosition);
    const APlayerController* Player=Cast<APlayerController>(Character->GetController());
    if (PreviousCharacter.Get()!=Character || Distance>180 || !Player || Player->IsMoveInputIgnored() ||
        Player->GetViewTarget()!=Character)
        DistanceSinceStep=0;
    else if (bGrounded)
    {
        if (!bWasGrounded) Step(Character,true);
        const float Speed=Character->GetVelocity().Size2D();
        if (Speed>45.f)
        {
            DistanceSinceStep+=Distance;
            const float Stride=FMath::GetMappedRangeValueClamped(FVector2D(120,560),FVector2D(76,153),Speed);
            if (DistanceSinceStep>=Stride)
            {
                DistanceSinceStep=FMath::Fmod(DistanceSinceStep,Stride);
                Step(Character,false);
            }
        }
    }
    else DistanceSinceStep=0;
    PreviousPosition=Position;
    PreviousCharacter=Character;
    bWasGrounded=bGrounded;
}

void UBrightonEnvironmentComponent::Step(ACharacter* Character,bool bLanding)
{
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BrightonFootstep),false,Character);
    Query.bReturnPhysicalMaterial=true;
    const FVector Start=Character->GetActorLocation();
    const float Depth=Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()+34.f;
    if (!GetWorld()->LineTraceSingleByChannel(Hit,Start,Start-FVector(0,0,Depth),ECC_Pawn,Query)) return;
    FString Surface;
    if (Hit.GetComponent())
        if (const UMaterialInterface* Material=Hit.GetComponent()->GetMaterial(0)) Surface=Material->GetName().ToLower();
    FName Kind=TEXT("Asphalt");
    if (Surface.Contains(TEXT("wood")) || Surface.Contains(TEXT("walnut")) || Surface.Contains(TEXT("floor"))) Kind=TEXT("Wood");
    else if (Surface.Contains(TEXT("tile"))) Kind=TEXT("Tile");
    else if (Wetness>.12f && (Surface.Contains(TEXT("wet")) || Director->IsRaining())) Kind=TEXT("Wet");
    const FBrightonFootsteps* Sounds=Data->Footsteps.Find(Kind);
    if (!Sounds || Sounds->Variations.IsEmpty()) return;
    int32 Index=Random.RandRange(0,Sounds->Variations.Num()-1);
    if (Index==LastVariation && Sounds->Variations.Num()>1) Index=(Index+1)%Sounds->Variations.Num();
    const float StepGain=FMath::GetMappedRangeValueClamped(FVector2D(100,560),FVector2D(.15,.23),
        Character->GetVelocity().Size2D());
    const float Gain=(bLanding ? .25f : StepGain)*Random.FRandRange(.9f,1.07f);
    UGameplayStatics::PlaySoundAtLocation(this,Sounds->Variations[Index],Hit.ImpactPoint,
        Gain,Random.FRandRange(.98f,1.02f));
    LastVariation=Index;
    LastSurface=Kind;
    ++FootstepCount;
}

void UBrightonEnvironmentComponent::UpdateWindowLights(const FVector& View)
{
    const APrologueTimeOfDay* Clock=Cast<APrologueTimeOfDay>(UGameplayStatics::GetActorOfClass(this,APrologueTimeOfDay::StaticClass()));
    const float Hour=Clock ? Clock->GetClockHour() : 22.f;
    const bool bNight=Hour>=17.f || Hour<7.f;
    for (const TWeakObjectPtr<ASpotLight>& Entry:WindowLights)
        if (Entry.IsValid()) Entry->GetLightComponent()->SetVisibility(bNight && FVector::DistSquared(View,Entry->GetActorLocation())<FMath::Square(2600.f));
}
