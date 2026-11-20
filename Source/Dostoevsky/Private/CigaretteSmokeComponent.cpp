#include "CigaretteSmokeComponent.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"

UCigaretteSmokeComponent::UCigaretteSmokeComponent()
{
    PrimaryComponentTick.bCanEverTick=true;
    PrimaryComponentTick.bStartWithTickEnabled=false;
    PrimaryComponentTick.TickInterval=.04f;
    SetMobility(EComponentMobility::Movable);
    SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SetCanEverAffectNavigation(false);
    SetCastShadow(false);
    bAffectDistanceFieldLighting=false;
    NumCustomDataFloats=1;
}

UCigaretteSmokeComponent* UCigaretteSmokeComponent::CreateTrail(AActor* Owner)
{
    auto* Trail=NewObject<UCigaretteSmokeComponent>(Owner);
    Trail->SetupAttachment(Owner->GetRootComponent());
    Trail->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane")));
    Trail->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Prologue/Brighton/Materials/M_CigaretteSmoke.M_CigaretteSmoke")));
    Trail->RegisterComponent();
    Trail->Random.Initialize(GetTypeHash(Owner->GetFName()));
    Trail->Puffs.SetNum(14);
    Trail->Transforms.Init(FTransform(FQuat::Identity,FVector::ZeroVector,FVector(.001f)),Trail->Puffs.Num());
    Trail->AddInstances(Trail->Transforms,false,false,false);
    Trail->SetVisibility(false);
    return Trail;
}

void UCigaretteSmokeComponent::SetSource(const FVector& Tip,const FVector& Mouth,const FVector& Forward,bool bExhaling)
{
    TipLocation=Tip;
    MouthLocation=Mouth;
    BreathDirection=Forward;
    bExhale=bExhaling;
    bEmitting=true;
    SetComponentTickEnabled(true);
}

void UCigaretteSmokeComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Delta,Type,Tick);
    const auto* Camera=UGameplayStatics::GetPlayerCameraManager(this,0);
    if (!Camera || GetOwner()->IsHidden() || FVector::DistSquared(Camera->GetCameraLocation(),TipLocation)>FMath::Square(1550.f))
    {
        if (IsVisible())
            for (int32 I=0;I<Puffs.Num();++I)
            {
                Puffs[I].Age=Puffs[I].Lifetime;
                SetCustomDataValue(I,0,0,false);
            }
        SetVisibility(false);
        SetComponentTickEnabled(false);
        return;
    }
    UntilNext-=Delta;
    if (bEmitting && UntilNext<=0)
    {
        const bool bBreath=bExhale && NextIndex%2==0;
        FPuff& Puff=Puffs[NextIndex];
        Puff.Age=0;
        Puff.Lifetime=Random.FRandRange(.85f,1.45f);
        Puff.Width=bBreath ? 8.5f : 2.7f;
        Puff.Phase=Random.FRandRange(0,2*PI);
        Puff.Location=bBreath ? MouthLocation : TipLocation;
        Puff.Velocity=FVector(3,2,Random.FRandRange(17.f,25.f));
        if (bBreath) Puff.Velocity+=BreathDirection*29.f;
        NextIndex=(NextIndex+1)%Puffs.Num();
        UntilNext=bExhale ? .11f : .15f;
    }
    bool bAlive=false;
    for (int32 I=0;I<Puffs.Num();++I)
    {
        FPuff& Puff=Puffs[I];
        if (Puff.Age>=Puff.Lifetime) continue;
        Puff.Age+=Delta;
        const float T=FMath::Min(1.f,Puff.Age/Puff.Lifetime);
        Puff.Location+=Delta*(Puff.Velocity+FVector(FMath::Sin(4*T+Puff.Phase)*6,FMath::Cos(5*T+Puff.Phase)*4,0));
        const FQuat Facing=FRotationMatrix::MakeFromZ(Camera->GetCameraLocation()-Puff.Location).ToQuat();
        const double Size=(.42+1.45*T)*Puff.Width/100.;
        Transforms[I]=FTransform(Facing,Puff.Location,FVector(Size,Size*1.24,Size));
        SetCustomDataValue(I,0,FMath::SmoothStep(0.f,.10f,T)*(1-FMath::SmoothStep(.24f,1.f,T)),false);
        bAlive|=T<1.f;
    }
    BatchUpdateInstancesTransforms(0,Transforms,true,true,true);
    SetVisibility(bAlive);
    if (!bAlive && !bEmitting) SetComponentTickEnabled(false);
}
