#include "CityCharacter.h"

#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#if WITH_EDITOR
#include "Animation/AnimData/AnimDataModel.h"
#include "Animation/AnimData/IAnimationDataController.h"
#include "Animation/AnimData/IAnimationDataModel.h"
#include "TwoBoneIK.h"

void UCityGestureSequence::UseRawBoneTracks()
{
    if (Cast<UAnimDataModel>(GetDataModelInterface().GetObject())) return;
    // These bakes contain only bone tracks and do not depend on an editor Control Rig.
    if (UObject* Previous=GetDataModelInterface().GetObject()) Previous->SetFlags(RF_Transient);
    Controller=nullptr;
    UAnimDataModel* Raw=NewObject<UAnimDataModel>(GetTransientPackage());
    CopyDataModel(TScriptInterface<IAnimationDataModel>(Raw));
}
#endif

void UCityCharacterProfile::Configure(USkeletalMeshComponent& Component) const
{
    Component.SetSkeletalMeshAsset(Mesh);
    Component.SetRelativeRotation(FRotator(0, FacingYaw, 0));
    Component.SetRelativeScale3D(FVector(ModelScale));
    for (int32 Index=0; Index<Materials.Num(); ++Index)
        if (Materials[Index]) Component.SetMaterial(Index, Materials[Index]);
    Component.SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component.SetCanEverAffectNavigation(false);
    Component.bEnableUpdateRateOptimizations=true;
    Component.VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
}

float UCityCharacterProfile::Play(USkeletalMeshComponent& Component, FName Motion, bool bLoop, float Rate) const
{
    const TObjectPtr<UAnimSequence>* Requested=Motions.Find(Motion);
    if (!Requested || !*Requested) Requested=Motions.Find(TEXT("Idle"));
    if (!Requested || !*Requested) return 0;
    UAnimSequence* Animation=Requested->Get();
    Component.PlayAnimation(Animation,bLoop);
    Component.SetPlayRate(Rate);
    return Animation->GetPlayLength()/FMath::Max(Rate,.01f);
}

#if WITH_EDITOR
namespace
{
int32 CityRigBone(const FReferenceSkeleton& Skeleton, const TCHAR* First, const TCHAR* Fallback=nullptr)
{
    int32 Index=Skeleton.FindBoneIndex(First);
    if (Index!=INDEX_NONE) return Index;
    Index=Skeleton.FindBoneIndex(FName(FString(First).Replace(TEXT("."),TEXT("_"))));
    return Index==INDEX_NONE && Fallback ? Skeleton.FindBoneIndex(Fallback) : Index;
}

void CitySamplePose(const FReferenceSkeleton& Skeleton, const IAnimationDataModel& Model, float Time,
    TArray<FTransform>& Local, TArray<FTransform>& ComponentSpace)
{
    const FFrameTime Frame=Model.GetFrameRate().AsFrameTime(FMath::Clamp(Time,0.f,static_cast<float>(Model.GetPlayLength())));
    const TArray<FTransform>& Reference=Skeleton.GetRefBonePose();
    Local.SetNum(Reference.Num());
    ComponentSpace.SetNum(Reference.Num());
    for (int32 Index=0; Index<Reference.Num(); ++Index)
    {
        const FName Name=Skeleton.GetBoneName(Index);
        Local[Index]=Model.IsValidBoneTrackName(Name)
            ? Model.EvaluateBoneTrackTransform(Name,Frame,EAnimInterpolationType::Linear) : Reference[Index];
        const int32 Parent=Skeleton.GetParentIndex(Index);
        ComponentSpace[Index]=Parent>=0 ? Local[Index]*ComponentSpace[Parent] : Local[Index];
    }
}

void CityReach(const FReferenceSkeleton& Skeleton, TArray<FTransform>& Local, const TArray<FTransform>& Pose,
    int32 Shoulder, int32 Elbow, int32 Hand, const FVector& Target, const FVector& Pole, double Weight)
{
    if (Shoulder<0 || Elbow<0 || Hand<0 || Weight<=0) return;
    FTransform Upper=Pose[Shoulder], Lower=Pose[Elbow], Wrist=Pose[Hand];
    AnimationCore::SolveTwoBoneIK(Upper,Lower,Wrist,Pole,FMath::Lerp(Wrist.GetLocation(),Target,Weight),false,1,1);
    Local[Shoulder]=Upper.GetRelativeTransform(Pose[Skeleton.GetParentIndex(Shoulder)]);
    Local[Elbow]=Lower.GetRelativeTransform(Upper);
}
}
#endif

FVector UCityCharacterAuthoring::PoseBonePosition(const USkeletalMesh* Mesh,const UAnimSequence* Animation,FName Bone,float Time)
{
#if WITH_EDITOR
    if (!Mesh || !Animation || !Animation->GetDataModel()) return FVector::ZeroVector;
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const int32 Index=CityRigBone(Ref,*Bone.ToString());
    if (Index!=INDEX_NONE)
    {
        TArray<FTransform> Local,Global;
        CitySamplePose(Ref,*Animation->GetDataModel(),Time,Local,Global);
        return Global[Index].GetLocation();
    }
#endif
    return FVector::ZeroVector;
}

bool UCityCharacterAuthoring::AuthorGesture(USkeletalMesh* Mesh,UAnimSequence* Idle,UCityGestureSequence* Destination,FName Gesture)
{
#if WITH_EDITOR
    if (!Mesh || !Idle || !Destination || !Idle->GetDataModel()) return false;
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const IAnimationDataModel& Model=*Idle->GetDataModel();
    const int32 Head=CityRigBone(Ref,TEXT("Head"));
    const int32 RightUpper=CityRigBone(Ref,TEXT("UpperArm.R"),TEXT("RightArm"));
    const int32 RightElbow=CityRigBone(Ref,TEXT("LowerArm.R"),TEXT("RightForeArm"));
    const int32 RightHand=CityRigBone(Ref,TEXT("MiddleHand.R"),TEXT("RightHand"));
    const int32 LeftUpper=CityRigBone(Ref,TEXT("UpperArm.L"),TEXT("LeftArm"));
    const int32 LeftElbow=CityRigBone(Ref,TEXT("LowerArm.L"),TEXT("LeftForeArm"));
    const int32 LeftHand=CityRigBone(Ref,TEXT("MiddleHand.L"),TEXT("LeftHand"));
    if (Head<0 || RightUpper<0 || LeftUpper<0 || RightElbow<0 || RightHand<0 || LeftElbow<0 || LeftHand<0)
        return false;

    const bool bSmoke=Gesture==TEXT("Smoke");
    const bool bTalk=Gesture==TEXT("Talk");
    const bool bNod=Gesture==TEXT("Nod");
    const bool bArmed=Gesture==TEXT("Armed");
    if (!bSmoke && !bTalk && !bNod && !bArmed) return false;
    constexpr int32 FramesPerSecond=30;
    const int32 FrameCount=bSmoke ? 216 : bTalk ? 126 : bNod ? 34 : 72;
    struct FGestureKeys
    {
        TArray<FVector> Positions;
        TArray<FQuat> Rotations;
        TArray<FVector> Scales;
    };
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    TArray<FTransform> Local,Pose;
    for (int32 Frame=0; Frame<=FrameCount; ++Frame)
    {
        const double Phase=double(Frame)/FrameCount;
        const float T=bNod ? 0.f : Idle->GetPlayLength()*Phase;
        CitySamplePose(Ref,Model,T,Local,Pose);
        const FVector Up=FVector::UpVector;
        const FVector Right=(Pose[RightUpper].GetLocation()-Pose[LeftUpper].GetLocation()).GetSafeNormal2D();
        const FVector Forward=FVector::CrossProduct(Right,Up).GetSafeNormal();
        const FVector HeadPosition=Pose[Head].GetLocation();
        const FVector Shoulders=(Pose[RightUpper].GetLocation()+Pose[LeftUpper].GetLocation())*.5;
        const double Width=FVector::Distance(Pose[RightUpper].GetLocation(),Pose[LeftUpper].GetLocation());
        const double Nod=FMath::Sin(PI*Phase)*FMath::Sin(PI*Phase);
        const double Puff=FMath::SmoothStep(.14,.29,Phase)*(1-FMath::SmoothStep(.52,.70,Phase));
        const double Speaking=FMath::Square(FMath::Sin(PI*Phase));
        if (bSmoke || bTalk || bArmed)
        {
            const FVector NearMouth=HeadPosition+Forward*Width*.26+Right*Width*.13-Up*Width*.01;
            const FVector TalkHand=Shoulders+Forward*Width*(.47+.08*FMath::Sin(4*PI*Phase))+
                Right*Width*.57-Up*Width*(.40+.15*FMath::Cos(4*PI*Phase));
            const FVector Reach=bSmoke ? NearMouth : bTalk ? TalkHand : Shoulders+Forward*Width*1.14+Right*Width*.14;
            const FVector Pole=Shoulders+Right*Width*1.1-Up*Width*.9;
            CityReach(Ref,Local,Pose,RightUpper,RightElbow,RightHand,Reach,Pole,
                bSmoke ? Puff : bTalk ? .72*Speaking : .94);
            if (bTalk || bArmed)
            {
                const FVector Other=Shoulders+Forward*Width*(bArmed ? 1.04 : .38)
                    -Right*Width*(bArmed ? .04 : .62)-Up*Width*(bArmed ? .12 : .51);
                CityReach(Ref,Local,Pose,LeftUpper,LeftElbow,LeftHand,Other,
                    Shoulders-Right*Width*1.1-Up*Width*.9,bArmed ? .94 : .32*Speaking);
            }
        }
        const double Tilt=bNod ? 12*Nod : bSmoke ? 6*Puff : bTalk ? 5*Speaking*FMath::Sin(6*PI*Phase) : -2;
        FTransform HeadPose=Pose[Head];
        HeadPose.SetRotation(FQuat(Right,FMath::DegreesToRadians(Tilt))*HeadPose.GetRotation());
        Local[Head]=HeadPose.GetRelativeTransform(Pose[Ref.GetParentIndex(Head)]);
        for (int32 Index=0; Index<Tracks.Num(); ++Index)
        {
            Tracks[Index].Positions.Add(Local[Index].GetTranslation());
            Tracks[Index].Rotations.Add(Local[Index].GetRotation().GetNormalized());
            Tracks[Index].Scales.Add(Local[Index].GetScale3D());
        }
    }

    Destination->SetSkeleton(Idle->GetSkeleton());
    Destination->SetPreviewMesh(Mesh);
    Destination->UseRawBoneTracks();
    IAnimationDataController& Controller=Destination->GetController();
    Controller.OpenBracket(NSLOCTEXT("CityLife","AuthorGesture","Bake character gesture"),false);
    Controller.SetFrameRate(FFrameRate(FramesPerSecond,1),false);
    Controller.SetNumberOfFrames(FFrameNumber(FrameCount),false);
    bool bValid=true;
    for (int32 Index=0; Index<Tracks.Num(); ++Index)
    {
        const FName Name=Ref.GetBoneName(Index);
        if (!Destination->GetDataModel()->IsValidBoneTrackName(Name))
            Controller.AddBoneCurve(Name,false);
        const FGestureKeys& Keys=Tracks[Index];
        bValid&=Controller.SetBoneTrackKeys(Name,Keys.Positions,Keys.Rotations,Keys.Scales,false);
    }
    Controller.NotifyPopulated();
    Controller.CloseBracket(false);
    Destination->MarkPackageDirty();
    return bValid;
#else
    return false;
#endif
}
