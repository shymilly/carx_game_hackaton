#include "CityCharacter.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#if WITH_EDITOR
#include "Algo/MaxElement.h"
#include "Animation/AnimData/AnimDataModel.h"
#include "Animation/AnimData/IAnimationDataController.h"
#include "Animation/AnimData/IAnimationDataModel.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/Skeleton.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_Slot.h"
#include "EdGraph/EdGraph.h"
#include "Engine/SkeletalMeshSocket.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Rendering/SkeletalMeshModel.h"
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

namespace
{
struct FCityClipProxy : FAnimSingleNodeInstanceProxy
{
    using FAnimSingleNodeInstanceProxy::FAnimSingleNodeInstanceProxy;
    TArray<FTransform> PreviousPose;
    float Elapsed = 0;
    float BlendSeconds = .21f;

    void PreUpdate(UAnimInstance* Instance,float Delta) override
    {
        FAnimSingleNodeInstanceProxy::PreUpdate(Instance,Delta);
        Elapsed+=Delta;
        if (Elapsed>=BlendSeconds) PreviousPose.Reset();
    }

    bool Evaluate(FPoseContext& Output) override
    {
        FAnimSingleNodeInstanceProxy::Evaluate(Output);
        if (!PreviousPose.IsEmpty())
        {
            const float Alpha=FMath::SmoothStep(0.f,BlendSeconds,Elapsed);
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            for (FCompactPoseBoneIndex Bone:Output.Pose.ForEachBoneIndex())
            {
                const int32 Index=Bones.MakeMeshPoseIndex(Bone).GetInt();
                if (PreviousPose.IsValidIndex(Index))
                {
                    const FTransform NewPose=Output.Pose[Bone];
                    Output.Pose[Bone].Blend(PreviousPose[Index],NewPose,Alpha);
                }
            }
        }
        return true;
    }
};
}

FAnimInstanceProxy* UCityClipInstance::CreateAnimInstanceProxy()
{
    return new FCityClipProxy(this);
}

void UCityClipInstance::TransitionTo(UAnimSequence* Clip,bool bLoop,float Rate,bool bMatchStride)
{
    float Start=0.f;
    if (GetCurrentAsset())
    {
        FCityClipProxy& Proxy=GetProxyOnGameThread<FCityClipProxy>();
        Proxy.PreviousPose=GetSkelMeshComponent()->GetBoneSpaceTransforms();
        Proxy.Elapsed=0;
        Proxy.BlendSeconds=bMatchStride ? .16f : .21f;
        if (bMatchStride && GetLength()>UE_SMALL_NUMBER)
            Start=FMath::Fmod(GetCurrentTime()/GetLength(),1.f)*Clip->GetPlayLength();
    }
    SetAnimationAsset(Clip,bLoop,Rate);
    PlayAnim(bLoop,Rate,Start);
}

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
    UCityClipInstance* Player=Cast<UCityClipInstance>(Component.GetAnimInstance());
    if (!Player)
    {
        Component.SetAnimInstanceClass(UCityClipInstance::StaticClass());
        Player=Cast<UCityClipInstance>(Component.GetAnimInstance());
    }
    if (!Player) return 0.f;
    const auto* Previous=Player->GetCurrentAsset();
    const bool bStride=(Motion==TEXT("Walk") || Motion==TEXT("Run")) && Previous &&
        (Previous==Motions.FindRef(TEXT("Walk")).Get() || Previous==Motions.FindRef(TEXT("Run")).Get());
    Player->TransitionTo(Animation,bLoop,Rate,bStride);
    return Animation->GetPlayLength()/FMath::Max(Rate,.01f);
}

#if WITH_EDITOR
namespace
{
int32 CityRigBone(const FReferenceSkeleton& Skeleton, const TCHAR* First,
    const TCHAR* Fallback=nullptr, const TCHAR* Alternate=nullptr)
{
    int32 Index=Skeleton.FindBoneIndex(First);
    if (Index!=INDEX_NONE) return Index;
    Index=Skeleton.FindBoneIndex(FName(FString(First).Replace(TEXT("."),TEXT("_"))));
    if (Index==INDEX_NONE && Fallback) Index=Skeleton.FindBoneIndex(Fallback);
    return Index==INDEX_NONE && Alternate ? Skeleton.FindBoneIndex(Alternate) : Index;
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
    AnimationCore::SolveTwoBoneIK(Upper,Lower,Wrist,Pole,Target,false,1,1);
    const FTransform RestUpper=Local[Shoulder], RestElbow=Local[Elbow];
    Local[Shoulder].Blend(RestUpper,Upper.GetRelativeTransform(Pose[Skeleton.GetParentIndex(Shoulder)]),Weight);
    Local[Elbow].Blend(RestElbow,Lower.GetRelativeTransform(Upper),Weight);
}

void ComponentPose(const FReferenceSkeleton& Ref,const TArray<FTransform>& Local,TArray<FTransform>& Pose)
{
    Pose.SetNum(Local.Num());
    for (int32 Index=0;Index<Local.Num();++Index)
    {
        const int32 Parent=Ref.GetParentIndex(Index);
        Pose[Index]=Parent==INDEX_NONE ? Local[Index] : Local[Index]*Pose[Parent];
    }
}

void SetMeshSocket(USkeletalMesh& Mesh,FName Name,FName Bone,const FTransform& Local)
{
    USkeletalMeshSocket* Socket=Mesh.FindSocket(Name);
    if (!Socket)
    {
        Socket=NewObject<USkeletalMeshSocket>(&Mesh,NAME_None,RF_Transactional);
        Socket->SocketName=Name;
        Mesh.AddSocket(Socket);
    }
    Socket->BoneName=Bone;
    Socket->RelativeLocation=Local.GetLocation();
    Socket->RelativeRotation=Local.Rotator();
    Socket->bForceAlwaysAnimated=true;
    Mesh.MarkPackageDirty();
}

FTransform CityGrip(const TArray<FTransform>& Pose,int32 Palm,int32 Fingers,int32 Thumb)
{
    const FVector Tip=Pose[Fingers].GetLocation();
    const FVector ThumbTip=Pose[Thumb].GetLocation();
    const FVector Knuckle=Pose[Palm].GetLocation();
    const FVector Axis=(Tip-Knuckle).GetSafeNormal();
    const FVector Grip=FMath::Lerp(Tip,ThumbTip,.45);
    return FTransform(FRotationMatrix::MakeFromXY(Axis,ThumbTip-Tip).ToQuat(),Grip)
        .GetRelativeTransform(Pose[Palm]);
}

FTransform CigarettePinch(const TArray<FTransform>& Pose,int32 Palm,int32 Knuckles,int32 Fingers,int32 Thumb)
{
    const FVector Hand=(Pose[Knuckles].GetLocation()-Pose[Palm].GetLocation()).GetSafeNormal();
    const FVector Pad=Pose[Fingers].GetLocation();
    const FVector ThumbTip=Pose[Thumb].GetLocation();
    const FVector Across=FVector::VectorPlaneProject(ThumbTip-Pad,Hand).GetSafeNormal();
    // The cigarette crosses the fingers. Its axis must not dictate the direction of the wrist.
    return FTransform(FRotationMatrix::MakeFromXY(Across,Hand).ToQuat(),FMath::Lerp(Pad,ThumbTip,.33))
        .GetRelativeTransform(Pose[Palm]);
}

FTransform SmokeMouthSocket(const USkeletalMesh& Mesh,const FTransform& HeadPose,int32 Head,
                           const FVector& Forward,const FVector& Right,double Width)
{
    const FVector Origin=HeadPose.GetLocation();
    const FVector Up=FVector::UpVector;
    double LipHeight=Width*.023, LipDepth=Width*.36;
    TArray<FVector2D> CenterLine;
    if (const FSkeletalMeshModel* Model=Mesh.GetImportedModel(); Model && !Model->LODModels.IsEmpty())
    {
        for (const FSkelMeshSection& Section:Model->LODModels[0].Sections)
        {
            for (const FSoftSkinVertex& Vertex:Section.SoftVertices)
            {
                const FVector Delta=FVector(Vertex.Position)-Origin;
                if (FMath::Abs(Delta.Dot(Right))>Width*.07 || FMath::Abs(Delta.Z)>Width*.27) continue;
                const double Depth=Delta.Dot(Forward);
                if (Depth<Width*.23) continue;
                for (int32 Index=0;Index<UE_ARRAY_COUNT(Vertex.InfluenceBones);++Index)
                {
                    const int32 Bone=Vertex.InfluenceBones[Index];
                    if (Vertex.InfluenceWeights[Index] && Section.BoneMap.IsValidIndex(Bone) && Section.BoneMap[Bone]==Head)
                    {
                        CenterLine.Emplace(Depth,Delta.Z);
                        break;
                    }
                }
            }
        }
    }
    if (!CenterLine.IsEmpty())
    {
        // On both imported male head meshes the central projection peaks at the nose.
        const FVector2D Nose=*Algo::MaxElementBy(CenterLine,[](const FVector2D& P){return P.X;});
        LipHeight=Nose.Y-Width*.085;
        LipDepth=Nose.X-Width*.040;
        for (const FVector2D& Point:CenterLine)
            if (FMath::Abs(Point.Y-LipHeight)<Width*.027) LipDepth=FMath::Max(LipDepth,Point.X);
    }
    const FVector Lip=Origin+Forward*(LipDepth+Width*.013)+Up*LipHeight;
    return FTransform(FRotationMatrix::MakeFromXZ(Forward,Up).ToQuat(),Lip).GetRelativeTransform(HeadPose);
}

void RotateWrist(const FReferenceSkeleton& Ref, TArray<FTransform>& Local,
                 TArray<FTransform>& Pose,int32 Wrist,const FQuat& Rotation)
{
    ComponentPose(Ref,Local,Pose);
    Local[Wrist].SetRotation(Pose[Ref.GetParentIndex(Wrist)].GetRotation().Inverse()*Rotation);
}

double GestureWindow(double Start,double End,double Phase)
{
    if (Phase<=Start || Phase>=End) return 0.;
    return FMath::Square(FMath::Sin(PI*(Phase-Start)/(End-Start)));
}

void TurnBone(const FReferenceSkeleton& Ref,TArray<FTransform>& Local,const TArray<FTransform>& Pose,
              int32 Bone,const FQuat& Rotation)
{
    if (Bone<0 || Ref.GetParentIndex(Bone)<0) return;
    FTransform Adjusted=Pose[Bone];
    Adjusted.SetRotation(Rotation*Adjusted.GetRotation());
    Local[Bone]=Adjusted.GetRelativeTransform(Pose[Ref.GetParentIndex(Bone)]);
}

void CloseCigaretteGrip(const FReferenceSkeleton& Ref,TArray<FTransform>& Local,TArray<FTransform>& Pose,
                        int32 Palm,int32 Knuckles,int32 Fingers,int32 ThumbBase,int32 ThumbTip)
{
    const FVector Hand=(Pose[Knuckles].GetLocation()-Pose[Palm].GetLocation()).GetSafeNormal();
    const FVector Across=FVector::VectorPlaneProject(Pose[ThumbTip].GetLocation()-Pose[Fingers].GetLocation(),Hand)
        .GetSafeNormal();
    TurnBone(Ref,Local,Pose,Fingers,FQuat(Across,FMath::DegreesToRadians(-38.)));
    if (ThumbBase>=0)
    {
        const FVector Thumb=Pose[ThumbBase].GetLocation();
        const FVector Original=(Pose[ThumbTip].GetLocation()-Thumb).GetSafeNormal();
        const FVector Target=(Pose[Fingers].GetLocation()-Thumb).GetSafeNormal();
        const FQuat Close=FQuat::FindBetweenNormals(Original,Target);
        TurnBone(Ref,Local,Pose,ThumbBase,FQuat::Slerp(FQuat::Identity,Close,.28));
    }
    ComponentPose(Ref,Local,Pose);
}

void CloseBottleGrip(const FReferenceSkeleton& Ref,TArray<FTransform>& Local,TArray<FTransform>& Pose)
{
    const int32 Index=CityRigBone(Ref,TEXT("index_01_r"));
    const int32 Little=CityRigBone(Ref,TEXT("pinky_01_r"));
    if (Index<0 || Little<0) return;
    const FVector Across=(Pose[Little].GetLocation()-Pose[Index].GetLocation()).GetSafeNormal();
    const double Angles[]={-28.,-43.,-27.};
    for (const TCHAR* Finger:{TEXT("index"),TEXT("middle"),TEXT("ring"),TEXT("pinky")})
    {
        for (int32 Joint=0;Joint<3;++Joint)
        {
            const FString Name=FString::Printf(TEXT("%s_0%d_r"),Finger,Joint+1);
            TurnBone(Ref,Local,Pose,CityRigBone(Ref,*Name),FQuat(Across,FMath::DegreesToRadians(Angles[Joint])));
            ComponentPose(Ref,Local,Pose);
        }
    }
}

struct FGestureKeys
{
    TArray<FVector> Positions;
    TArray<FQuat> Rotations;
    TArray<FVector> Scales;
};

void AppendGesturePose(const TArray<FTransform>& Local,TArray<FGestureKeys>& Tracks)
{
    for (int32 Index=0;Index<Tracks.Num();++Index)
    {
        Tracks[Index].Positions.Add(Local[Index].GetTranslation());
        Tracks[Index].Rotations.Add(Local[Index].GetRotation().GetNormalized());
        Tracks[Index].Scales.Add(Local[Index].GetScale3D());
    }
}

bool WriteGesture(USkeletalMesh& Mesh,UCityGestureSequence& Destination,const TArray<FGestureKeys>& Tracks,int32 FrameCount)
{
    Destination.SetSkeleton(Mesh.GetSkeleton());
    Destination.SetPreviewMesh(&Mesh);
    Destination.UseRawBoneTracks();
    IAnimationDataController& Controller=Destination.GetController();
    Controller.OpenBracket(NSLOCTEXT("CityLife","AuthorGesture","Bake character gesture"),false);
    Controller.SetFrameRate(FFrameRate(30,1),false);
    Controller.SetNumberOfFrames(FFrameNumber(FrameCount),false);
    bool bValid=true;
    for (int32 Index=0;Index<Tracks.Num();++Index)
    {
        const FName Name=Mesh.GetRefSkeleton().GetBoneName(Index);
        if (!Destination.GetDataModel()->IsValidBoneTrackName(Name))
            Controller.AddBoneCurve(Name,false);
        const FGestureKeys& Keys=Tracks[Index];
        bValid&=Controller.SetBoneTrackKeys(Name,Keys.Positions,Keys.Rotations,Keys.Scales,false);
    }
    Controller.NotifyPopulated();
    Controller.CloseBracket(false);
    Destination.MarkPackageDirty();
    return bValid;
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

bool UCityCharacterAuthoring::FixRetargetedBoneUnits(const USkeletalMesh* Mesh,UAnimSequence* Animation,FName PelvisBone)
{
#if WITH_EDITOR
    if (!Mesh || !Animation || Mesh->GetSkeleton()!=Animation->GetSkeleton() || !Animation->GetDataModel()) return false;
    const FReferenceSkeleton& Skeleton=Mesh->GetRefSkeleton();
    const IAnimationDataModel& Model=*Animation->GetDataModel();
    IAnimationDataController& Controller=Animation->GetController();
    TArray<FName> Names;
    Model.GetBoneTrackNames(Names);
    Controller.OpenBracket(NSLOCTEXT("CityLife","RetargetScale","Keep the target rig's bone scale"),false);
    bool bSuccess=!Names.IsEmpty();
    for (const FName Name:Names)
    {
        const int32 Index=Skeleton.FindBoneIndex(Name);
        if (Index==INDEX_NONE) continue;
        TArray<FTransform> Keys;
        Model.GetBoneTrackTransforms(Name,Keys);
        const FTransform& Reference=Skeleton.GetRefBonePose()[Index];
        const int32 ParentIndex=Skeleton.GetParentIndex(Index);
        // A metre-based FBX can keep its conversion on the root. The IK bake writes the pelvis in cm.
        const bool bConvertPelvis=Name==PelvisBone && ParentIndex>=0 && !Keys.IsEmpty() &&
            Keys[0].GetTranslation().Size()>Reference.GetTranslation().Size()*10.0;
        const FVector Units=bConvertPelvis ? Skeleton.GetRefBonePose()[ParentIndex].GetScale3D() : FVector::OneVector;
        TArray<FVector> Positions,Scales;
        TArray<FQuat> Rotations;
        Positions.Reserve(Keys.Num());
        Rotations.Reserve(Keys.Num());
        for (const FTransform& Key:Keys)
        {
            Positions.Add(Key.GetTranslation()/Units);
            Rotations.Add(Key.GetRotation());
        }
        Scales.Init(Reference.GetScale3D(),Keys.Num());
        bSuccess&=Controller.SetBoneTrackKeys(Name,Positions,Rotations,Scales,false);
    }
    Controller.CloseBracket(false);
    Animation->MarkPackageDirty();
    return bSuccess;
#else
    return false;
#endif
}

bool UCityCharacterAuthoring::RemoveLocomotionTravel(const USkeletalMesh* Mesh,UAnimSequence* Animation,FName PelvisBone)
{
#if WITH_EDITOR
    if (!Mesh || !Animation || Mesh->GetSkeleton()!=Animation->GetSkeleton()) return false;
    const FReferenceSkeleton& Skeleton=Mesh->GetRefSkeleton();
    const int32 PelvisIndex=Skeleton.FindBoneIndex(PelvisBone);
    const IAnimationDataModel* Model=Animation->GetDataModel();
    if (PelvisIndex==INDEX_NONE || Skeleton.GetParentIndex(PelvisIndex)!=0 ||
        !Model || !Model->IsValidBoneTrackName(PelvisBone)) return false;

    TArray<FTransform> Keys;
    Model->GetBoneTrackTransforms(PelvisBone,Keys);
    if (Keys.Num()<2) return false;
    const FTransform& Root=Skeleton.GetRefBonePose()[0];
    FVector Travel=Root.TransformVector(Keys.Last().GetTranslation()-Keys[0].GetTranslation());
    Travel.Z=0;
    if (Travel.IsNearlyZero(.01)) return true;
    const FVector LocalTravel=Root.InverseTransformVector(Travel);

    FGestureKeys InPlace;
    for (int32 Index=0;Index<Keys.Num();++Index)
    {
        const double Progress=double(Index)/(Keys.Num()-1);
        InPlace.Positions.Add(Keys[Index].GetTranslation()-LocalTravel*Progress);
        InPlace.Rotations.Add(Keys[Index].GetRotation());
        InPlace.Scales.Add(Keys[Index].GetScale3D());
    }
    IAnimationDataController& Controller=Animation->GetController();
    const bool bChanged=Controller.SetBoneTrackKeys(
        PelvisBone,InPlace.Positions,InPlace.Rotations,InPlace.Scales,false);
    if (bChanged) Animation->MarkPackageDirty();
    return bChanged;
#else
    return false;
#endif
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
    const int32 RightHand=CityRigBone(Ref,TEXT("MiddleHand.R"),TEXT("RightHand"),TEXT("hand_r"));
    const int32 LeftUpper=CityRigBone(Ref,TEXT("UpperArm.L"),TEXT("LeftArm"));
    const int32 LeftElbow=CityRigBone(Ref,TEXT("LowerArm.L"),TEXT("LeftForeArm"));
    const int32 LeftHand=CityRigBone(Ref,TEXT("MiddleHand.L"),TEXT("LeftHand"),TEXT("hand_l"));
    if (Head<0 || RightUpper<0 || LeftUpper<0 || RightElbow<0 || RightHand<0 || LeftElbow<0 || LeftHand<0)
        return false;

    const bool bSmoke=Gesture==TEXT("Smoke");
    const bool bSeatedTalk=Gesture==TEXT("SeatedTalk");
    const bool bSeatedNod=Gesture==TEXT("SeatedNod");
    const bool bSeat=Gesture==TEXT("SeatedIdle") || bSeatedTalk || bSeatedNod;
    const bool bBottle=Gesture==TEXT("HoldBottle") || Gesture==TEXT("TalkWithBottle");
    const bool bTalk=Gesture==TEXT("Talk") || Gesture==TEXT("TalkWithBottle") || bSeatedTalk;
    const bool bNod=Gesture==TEXT("Nod") || bSeatedNod;
    const bool bArmed=Gesture==TEXT("Armed");
    const bool bShot=Gesture==TEXT("Shot");
    if (!bSmoke && !bTalk && !bSeat && !bBottle && !bNod && !bArmed && !bShot) return false;
    const int32 FrameCount=bSmoke ? 216 : bNod ? 34 : (bTalk || bSeat || bBottle) ? 168 : bShot ? 45 : 72;
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    TArray<FTransform> Local,Pose;
    const int32 Palm=CityRigBone(Ref,TEXT("Palm_R"),TEXT("hand_r"));
    const int32 LeftPalm=CityRigBone(Ref,TEXT("Palm_L"),TEXT("LeftHand"),TEXT("hand_l"));
    const int32 Knuckles=Palm==RightHand ? CityRigBone(Ref,TEXT("middle_01_r")) : RightHand;
    const int32 Fingers=CityRigBone(Ref,TEXT("Fingers_R"),TEXT("middle_03_r"));
    const int32 Thumb=CityRigBone(Ref,TEXT("Thumb2_R"),TEXT("thumb_03_r"));
    const int32 ThumbBase=CityRigBone(Ref,TEXT("Thumb1_R"),TEXT("thumb_01_r"));
    const int32 Chest=CityRigBone(Ref,TEXT("Torso"),TEXT("Spine2"),TEXT("spine_03"));
    const int32 Shoulder=CityRigBone(Ref,TEXT("Shoulder_R"),TEXT("clavicle_r"));
    FTransform Grip,Mouth;
    if (bSmoke || bBottle)
    {
        if (Palm<0 || Knuckles<0 || Fingers<0 || Thumb<0) return false;
        Local=Ref.GetRefBonePose();
        ComponentPose(Ref,Local,Pose);
        if (bSmoke) CloseCigaretteGrip(Ref,Local,Pose,Palm,Knuckles,Fingers,ThumbBase,Thumb);
        else CloseBottleGrip(Ref,Local,Pose);
        Grip=bSmoke ? CigarettePinch(Pose,Palm,Knuckles,Fingers,Thumb) : CityGrip(Pose,Palm,Fingers,Thumb);
        SetMeshSocket(*Mesh,bSmoke ? TEXT("CigaretteGrip") : TEXT("BottleGrip"),Ref.GetBoneName(Palm),Grip);
    }
    if (bSmoke)
    {
        const double Width=FVector::Dist(Pose[RightUpper].GetLocation(),Pose[LeftUpper].GetLocation());
        const FVector Right=(Pose[RightUpper].GetLocation()-Pose[LeftUpper].GetLocation()).GetSafeNormal2D();
        const FVector Forward=FVector::CrossProduct(Right,FVector::UpVector);
        Mouth=SmokeMouthSocket(*Mesh,Pose[Head],Head,Forward,Right,Width);
        SetMeshSocket(*Mesh,TEXT("SmokeMouth"),Ref.GetBoneName(Head),Mouth);
    }
    for (int32 Frame=0; Frame<=FrameCount; ++Frame)
    {
        const double Phase=double(Frame)/FrameCount;
        const double Breath=FMath::Square(FMath::Sin(2*PI*Phase));
        float T=Idle->GetPlayLength()*Phase;
        if (bSeat) T=FMath::Min(2.3f,Idle->GetPlayLength());
        else if (bNod) T=0;
        else if (bTalk || bSmoke || bBottle) T=Idle->GetPlayLength()*(.24+.36*Breath);
        CitySamplePose(Ref,Model,T,Local,Pose);
        if (bSmoke) CloseCigaretteGrip(Ref,Local,Pose,Palm,Knuckles,Fingers,ThumbBase,Thumb);
        if (bBottle) CloseBottleGrip(Ref,Local,Pose);
        const FVector Up=FVector::UpVector;
        const FVector Right=(Pose[RightUpper].GetLocation()-Pose[LeftUpper].GetLocation()).GetSafeNormal2D();
        const FVector Forward=FVector::CrossProduct(Right,Up).GetSafeNormal();
        const double Emphasis=bTalk ? .80*GestureWindow(.07,.27,Phase)+GestureWindow(.28,.49,Phase) : 0.;
        const double Acknowledge=GestureWindow(.65,.88,Phase);
        const double Puff=bSmoke ? FMath::SmoothStep(.13,.34,Phase)*(1-FMath::SmoothStep(.49,.73,Phase)) : 0.;
        const double Exhale=bSmoke ? GestureWindow(.605,.755,Phase) : 0.;
        if (bTalk || bSeat || bSmoke || bBottle)
        {
            TurnBone(Ref,Local,Pose,Chest,FQuat(Up,FMath::DegreesToRadians(3.*Emphasis-1.6*Puff))
                *FQuat(Right,FMath::DegreesToRadians(1.2*Breath)));
            ComponentPose(Ref,Local,Pose);
            TurnBone(Ref,Local,Pose,Head,FQuat(Up,FMath::DegreesToRadians(3.2*Emphasis-2.8*Acknowledge))
                *FQuat(Right,FMath::DegreesToRadians(3.5*Puff-3.5*Acknowledge+2.6*Emphasis-4.*Exhale)));
            ComponentPose(Ref,Local,Pose);
        }
        if (bSmoke)
        {
            TurnBone(Ref,Local,Pose,Shoulder,FQuat(Up,FMath::DegreesToRadians(-5.*Puff))
                *FQuat(Forward,FMath::DegreesToRadians(2.5*Puff)));
            ComponentPose(Ref,Local,Pose);
        }
        const FVector Shoulders=(Pose[RightUpper].GetLocation()+Pose[LeftUpper].GetLocation())*.5;
        const double Width=FVector::Distance(Pose[RightUpper].GetLocation(),Pose[LeftUpper].GetLocation());
        const double Kick=bShot ? FMath::SmoothStep(.318,.35,Phase)*(1.-FMath::SmoothStep(.36,.56,Phase)) : 0.;
        const double Present=bShot ? FMath::SmoothStep(0.,.22,Phase)*(1.-.65*FMath::SmoothStep(.65,1.,Phase)) : 1.;
        if (bSmoke)
        {
            const FTransform RestGrip=Grip*Pose[Palm];
            const FTransform Lips=Mouth*Pose[Head];
            const FVector Direction=(Lips.GetUnitAxis(EAxis::X)+Right*.29-Up*.06).GetSafeNormal();
            const FQuat Raised=FRotationMatrix::MakeFromXY(Direction,Up*.63-Right*.78).ToQuat();
            const double Turn=FMath::SmoothStep(.03,.96,Puff);
            const FQuat Wrist=FQuat::Slerp(RestGrip.GetRotation(),Raised,Turn)*Grip.GetRotation().Inverse();
            const FVector ByLips=Lips.GetLocation()+Direction*Width*.080;
            const FVector AtRest=RestGrip.GetLocation()+(Forward*.12+Right*.065+Up*.12)*Width;
            // Raise in front of the ribcage, with clearance for the forearm as it turns in toward the lips.
            const FVector Arc=(Forward*.57+Right*.20)*Width*(4.*Puff*(1.-Puff));
            const FVector SocketLocation=FMath::Lerp(AtRest,ByLips,Puff)+Arc;
            const FVector Hand=SocketLocation-Wrist.RotateVector(Grip.GetLocation()*Pose[Palm].GetScale3D());
            CityReach(Ref,Local,Pose,RightUpper,RightElbow,Palm,Hand,
                Pose[RightUpper].GetLocation()+(Right*.76+Forward*.57-Up*1.09)*Width,1.);
            RotateWrist(Ref,Local,Pose,Palm,Wrist);
        }
        else if (bTalk || bBottle)
        {
            if (bBottle)
            {
                const FVector BottleUp=(Up+Forward*.14+Right*.09).GetSafeNormal();
                const FQuat Wrist=FRotationMatrix::MakeFromZX(BottleUp,Forward).ToQuat()*Grip.GetRotation().Inverse();
                const FVector Socket=Shoulders+Forward*Width*(.36+.12*Emphasis)+Right*Width*.66
                    -Up*Width*(1.01-.12*Emphasis);
                CityReach(Ref,Local,Pose,RightUpper,RightElbow,Palm,
                    Socket-Wrist.RotateVector(Grip.GetLocation()*Pose[Palm].GetScale3D()),
                    Pose[RightUpper].GetLocation()+(Right*.35+Forward*.18-Up*1.12)*Width,1.);
                RotateWrist(Ref,Local,Pose,Palm,Wrist);
            }
            else if (bTalk)
            {
                const FVector Hand=Shoulders+Forward*Width*(.48+.10*Emphasis)+Right*Width*.57
                    -Up*Width*(.81-.20*Emphasis);
                CityReach(Ref,Local,Pose,RightUpper,RightElbow,Palm>=0 ? Palm : RightHand,Hand,
                    Shoulders+Right*Width*.83-Up*Width*.93,(bSeat ? .40 : .62)*Emphasis);
            }
            const double Reply=bBottle ? Emphasis : GestureWindow(.34,.50,Phase)*.54;
            const FVector Other=Shoulders+Forward*Width*.37-Right*Width*.58-Up*Width*.86;
            CityReach(Ref,Local,Pose,LeftUpper,LeftElbow,LeftPalm>=0 ? LeftPalm : LeftHand,Other,
                Shoulders-Right*Width*.87-Up*Width*.98,.49*Reply);
        }
        else if (bArmed || bShot)
        {
            const FVector Reach=Shoulders+Forward*Width*(1.14-.30*Kick)+Right*Width*.14+Up*Width*.25*Kick;
            const FVector Pole=Shoulders+Right*Width*1.1-Up*Width*.9;
            CityReach(Ref,Local,Pose,RightUpper,RightElbow,RightHand,Reach,Pole,.94*Present);
            const FVector Other=Shoulders+Forward*Width*(1.04-.30*Kick)-Right*Width*.04-Up*Width*(.12-.25*Kick);
            CityReach(Ref,Local,Pose,LeftUpper,LeftElbow,LeftHand,Other,
                Shoulders-Right*Width*1.1-Up*Width*.9,.94*Present);
        }
        if (bNod || bArmed || bShot)
        {
            const double Tilt=bNod ? 8.5*GestureWindow(.08,.83,Phase) : -2.;
            if (bSeatedNod) ComponentPose(Ref,Local,Pose);
            TurnBone(Ref,Local,Pose,Head,FQuat(Right,FMath::DegreesToRadians(Tilt)));
        }
        AppendGesturePose(Local,Tracks);
    }
    return WriteGesture(*Mesh,*Destination,Tracks,FrameCount);
#else
    return false;
#endif
}

bool UCityCharacterAuthoring::AuthorBarPistolPose(USkeletalMesh* Mesh,UAnimSequence* Idle,UCityGestureSequence* Destination)
{
#if WITH_EDITOR
    if (!Mesh || !Idle || !Destination || !Idle->GetDataModel()) return false;
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const auto Bone=[&Ref](const TCHAR* Name) { return Ref.FindBoneIndex(Name); };
    const int32 RightUpper=Bone(TEXT("UpperArm_R")), RightElbow=Bone(TEXT("LowerArm_R")), RightHand=Bone(TEXT("Hand_R"));
    const int32 LeftUpper=Bone(TEXT("UpperArm_L")), LeftElbow=Bone(TEXT("LowerArm_L")), LeftHand=Bone(TEXT("Hand_L"));
    const int32 Index=Bone(TEXT("Index1_R")), Middle=Bone(TEXT("Middle1_R")), Little=Bone(TEXT("Little1_R"));
    const int32 Thumb=Bone(TEXT("Thumb2_R"));
    if (FMath::Min3(RightUpper,RightElbow,RightHand)<0 || FMath::Min3(LeftUpper,LeftElbow,LeftHand)<0 ||
        FMath::Min3(Index,Middle,Little)<0 || Thumb<0) return false;

    TArray<FTransform> Local,Pose;
    const IAnimationDataModel& Model=*Idle->GetDataModel();
    CitySamplePose(Ref,Model,0,Local,Pose);
    const FVector Along=(Pose[Middle].GetLocation()-Pose[RightHand].GetLocation()).GetSafeNormal();
    const FVector Across=(Pose[Index].GetLocation()-Pose[Little].GetLocation()).GetSafeNormal();
    const FVector HandCenter=FMath::Lerp(Pose[RightHand].GetLocation(),Pose[Middle].GetLocation(),.72);
    const FVector CurlNormal=FVector::CrossProduct(Across,Along).GetSafeNormal();
    const double CurlSign=CurlNormal.Dot(Pose[Thumb].GetLocation()-HandCenter)<0 ? -1. : 1.;
    const FVector Center=HandCenter+CurlNormal*(CurlSign*.9);
    const FTransform Grip=FTransform(FRotationMatrix::MakeFromXZ(Along,Across).ToQuat(),Center)
        .GetRelativeTransform(Pose[RightHand]);
    SetMeshSocket(*Mesh,TEXT("BarPistolGrip"),Ref.GetBoneName(RightHand),Grip);

    constexpr int32 Frames=45;
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    for (int32 Frame=0;Frame<=Frames;++Frame)
    {
        const double T=Frame/30.;
        CitySamplePose(Ref,Model,T*.36,Local,Pose);
        const double Lift=FMath::SmoothStep(.02,.31,T)*(1.-FMath::SmoothStep(.91,1.50,T));
        const double Recoil=FMath::SmoothStep(.47,.51,T)*(1.-FMath::SmoothStep(.52,.78,T));
        const FVector Up=FVector::UpVector;
        const FVector Right=(Pose[RightUpper].GetLocation()-Pose[LeftUpper].GetLocation()).GetSafeNormal2D();
        const FVector Forward=FVector::CrossProduct(Right,Up);
        const FVector Shoulders=(Pose[LeftUpper].GetLocation()+Pose[RightUpper].GetLocation())*.5;
        const double Width=FVector::Dist(Pose[LeftUpper].GetLocation(),Pose[RightUpper].GetLocation());
        const FVector Aim=(Forward+Up*(.025+.19*Recoil)).GetSafeNormal();
        const FQuat PropRotation=FRotationMatrix::MakeFromXZ(Aim,Up).ToQuat();
        const FQuat AimWrist=PropRotation*Grip.GetRotation().Inverse();
        const FQuat Wrist=FQuat::Slerp(Pose[RightHand].GetRotation(),AimWrist,Lift);
        const FVector GripPoint=Shoulders+Forward*Width*(1.25-.13*Recoil)+Right*Width*.055-Up*Width*.22;
        const FVector Hand=GripPoint-AimWrist.RotateVector(Grip.GetLocation()*Pose[RightHand].GetScale3D());
        CityReach(Ref,Local,Pose,RightUpper,RightElbow,RightHand,Hand,Shoulders+Right*Width-Up*Width*.93,Lift);
        RotateWrist(Ref,Local,Pose,RightHand,Wrist);
        ComponentPose(Ref,Local,Pose);
        const FTransform PropSocket=Grip*Pose[RightHand];
        const FVector Support=PropSocket.GetLocation()-Forward*5.5-Right*5.2-Up*3.2;
        CityReach(Ref,Local,Pose,LeftUpper,LeftElbow,LeftHand,Support,Shoulders-Right*Width-Up*Width*.93,Lift);
        ComponentPose(Ref,Local,Pose);

        for (const TCHAR* Finger:{TEXT("Middle"),TEXT("Ring"),TEXT("Little")})
        {
            constexpr double Bend[]={19.,42.,24.};
            for (int32 Joint=0;Joint<UE_ARRAY_COUNT(Bend);++Joint)
            {
                const FString Name=FString::Printf(TEXT("%s%d_R"),Finger,Joint+1);
                TurnBone(Ref,Local,Pose,Bone(*Name),FQuat(PropSocket.GetUnitAxis(EAxis::Z),
                    FMath::DegreesToRadians(Bend[Joint]*Lift*CurlSign)));
                ComponentPose(Ref,Local,Pose);
            }
        }
        AppendGesturePose(Local,Tracks);
    }
    return WriteGesture(*Mesh,*Destination,Tracks,Frames);
#else
    return false;
#endif
}

bool UCityCharacterAuthoring::AuthorFirstPersonSmoke(USkeletalMesh* Mesh,USkeleton* Skeleton,UCityGestureSequence* Destination)
{
#if WITH_EDITOR
    if (!Mesh || !Skeleton || !Destination || !Skeleton->MergeAllBonesToBoneTree(Mesh,false)) return false;
    Mesh->SetSkeleton(Skeleton);
    Skeleton->MarkPackageDirty();
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const auto Bone=[&Ref](const TCHAR* Name){return Ref.FindBoneIndex(Name);};
    const int32 Upper=Bone(TEXT("upper_arm_R")), Elbow=Bone(TEXT("forearm_R")), Hand=Bone(TEXT("hand_R"));
    const int32 LeftUpper=Bone(TEXT("upper_arm_L")), LeftElbow=Bone(TEXT("forearm_L")), LeftHand=Bone(TEXT("hand_L"));
    const int32 Index=Bone(TEXT("f_index_03_R")), Middle=Bone(TEXT("f_middle_03_R"));
    const int32 IndexBase=Bone(TEXT("f_index_01_R")), MiddleBase=Bone(TEXT("f_middle_01_R"));
    if (FMath::Min3(Upper,Elbow,Hand)<0 || FMath::Min3(LeftUpper,LeftElbow,LeftHand)<0 ||
        FMath::Min3(Index,Middle,IndexBase)<0 || MiddleBase<0) return false;
    TArray<FTransform> Reference=Ref.GetRefBonePose();
    TArray<FTransform> Pose;
    ComponentPose(Ref,Reference,Pose);
    const FVector CurlAxis=(Pose[Middle].GetLocation()-Pose[Index].GetLocation()).GetSafeNormal();
    const auto Curl=[&](const TCHAR* Name,double Degrees)
    {
        const int32 Joint=Bone(Name);
        if (Joint>=0)
        {
            const FVector Axis=Pose[Ref.GetParentIndex(Joint)].InverseTransformVectorNoScale(CurlAxis);
            Reference[Joint].SetRotation(FQuat(Axis,FMath::DegreesToRadians(Degrees))*Reference[Joint].GetRotation());
        }
    };
    Curl(TEXT("f_ring_01_R"),38.);
    Curl(TEXT("f_ring_02_R"),51.);
    Curl(TEXT("f_ring_03_R"),17.);
    Curl(TEXT("f_pinky_01_R"),44.);
    Curl(TEXT("f_pinky_02_R"),54.);
    Curl(TEXT("f_pinky_03_R"),19.);
    for (const TCHAR* Name : {TEXT("f_index_02_R"),TEXT("f_middle_02_R")})
        Curl(Name,14.);
    ComponentPose(Ref,Reference,Pose);
    const FVector Near=FMath::Lerp(Pose[Index].GetLocation(),Pose[Middle].GetLocation(),.52);
    const FVector Base=(Pose[IndexBase].GetLocation()+Pose[MiddleBase].GetLocation())*.5;
    const FVector AlongFingers=(Near-Base).GetSafeNormal();
    const FVector ThroughGrip=FVector::CrossProduct(AlongFingers,CurlAxis).GetSafeNormal();
    const FTransform Grip=FTransform(FRotationMatrix::MakeFromXY(ThroughGrip,AlongFingers).ToQuat(),Near)
        .GetRelativeTransform(Pose[Hand]);
    SetMeshSocket(*Mesh,TEXT("CigaretteGrip"),Ref.GetBoneName(Hand),Grip);
    constexpr int32 Frames=78;
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    for (int32 Frame=0;Frame<=Frames;++Frame)
    {
        const double Seconds=Frame/30.;
        const double Lift=FMath::SmoothStep(.10,.86,Seconds)*(1.-FMath::SmoothStep(1.39,2.38,Seconds));
        TArray<FTransform> Local=Reference;
        ComponentPose(Ref,Local,Pose);
        CityReach(Ref,Local,Pose,LeftUpper,LeftElbow,LeftHand,FVector(28,14,117),FVector(47,0,112),1.);
        const FVector Position=FMath::Lerp(FVector(-26,39,127),FVector(-13,38,164),Lift);
        const FVector Axis=FMath::Lerp(FVector(-.40,.77,.24),FVector(-.84,.37,.09),Lift);
        const FQuat Wrist=FRotationMatrix::MakeFromXY(Axis,FVector(-.22,-.19,.96)).ToQuat()*Grip.GetRotation().Inverse();
        const FVector Target=Position-Wrist.RotateVector(Grip.GetLocation()*Pose[Hand].GetScale3D());
        CityReach(Ref,Local,Pose,Upper,Elbow,Hand,Target,FVector(-41,9,115),1.);
        RotateWrist(Ref,Local,Pose,Hand,Wrist);
        AppendGesturePose(Local,Tracks);
    }
    return WriteGesture(*Mesh,*Destination,Tracks,Frames);
#else
    return false;
#endif
}

bool UCityCharacterAuthoring::AuthorFirstPersonTrip(USkeletalMesh* Mesh,UCityGestureSequence* Destination)
{
#if WITH_EDITOR
    if (!Mesh || !Mesh->GetSkeleton() || !Destination) return false;
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const auto Bone=[&Ref](const TCHAR* Name){return Ref.FindBoneIndex(Name);};
    const int32 UpperL=Bone(TEXT("upper_arm_L")), ElbowL=Bone(TEXT("forearm_L")), HandL=Bone(TEXT("hand_L"));
    const int32 UpperR=Bone(TEXT("upper_arm_R")), ElbowR=Bone(TEXT("forearm_R")), HandR=Bone(TEXT("hand_R"));
    if (FMath::Min3(UpperL,ElbowL,HandL)<0 || FMath::Min3(UpperR,ElbowR,HandR)<0) return false;
    const TArray<FTransform>& Reference=Ref.GetRefBonePose();
    TArray<FTransform> Pose;
    constexpr int32 Frames=58;
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    for (int32 Frame=0;Frame<=Frames;++Frame)
    {
        const double Time=Frame/30.;
        const double Reach=FMath::SmoothStep(.03,.36,Time);
        const double Brace=FMath::SmoothStep(.36,.64,Time);
        const double Push=FMath::SmoothStep(.91,1.20,Time);
        const double Release=FMath::SmoothStep(1.12,1.76,Time);
        FVector Left=FMath::Lerp(FVector(37,10,112),FVector(25,55,159),Reach);
        FVector Right=FMath::Lerp(FVector(-39,13,115),FVector(-31,51,156),Reach);
        Left=FMath::Lerp(Left,FVector(25,49,150),Brace)+FVector(2,-6,-4)*Push;
        Right=FMath::Lerp(Right,FVector(-31,45,152),Brace)+FVector(-3,-7,-5)*Push;
        Left=FMath::Lerp(Left,FVector(37,11,112),Release);
        Right=FMath::Lerp(Right,FVector(-38,13,115),Release);
        TArray<FTransform> Local=Reference;
        ComponentPose(Ref,Local,Pose);
        CityReach(Ref,Local,Pose,UpperL,ElbowL,HandL,Left,FVector(54,24,112),1.);
        CityReach(Ref,Local,Pose,UpperR,ElbowR,HandR,Right,FVector(-56,22,114),1.);
        AppendGesturePose(Local,Tracks);
    }
    return WriteGesture(*Mesh,*Destination,Tracks,Frames);
#else
    return false;
#endif
}

bool UCityCharacterAuthoring::AuthorFirstPersonRecorder(USkeletalMesh* Mesh,UCityGestureSequence* Destination,FVector& ContactPoint)
{
#if WITH_EDITOR
    if (!Mesh || !Mesh->GetSkeleton() || !Destination) return false;
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const int32 Upper=CityRigBone(Ref,TEXT("upper_arm_R"));
    const int32 Elbow=CityRigBone(Ref,TEXT("forearm_R"));
    const int32 Hand=CityRigBone(Ref,TEXT("hand_R"));
    const int32 Index=CityRigBone(Ref,TEXT("f_index_03_R"));
    const int32 IndexBase=CityRigBone(Ref,TEXT("f_index_01_R"));
    const int32 Middle=CityRigBone(Ref,TEXT("f_middle_01_R"));
    if (FMath::Min3(Upper,Elbow,Hand)<0 || FMath::Min3(Index,IndexBase,Middle)<0) return false;

    TArray<FTransform> Fingers=Ref.GetRefBonePose();
    TArray<FTransform> Pose;
    ComponentPose(Ref,Fingers,Pose);
    const FVector Along=(Pose[Index].GetLocation()-Pose[IndexBase].GetLocation()).GetSafeNormal();
    const FVector Across=(Pose[Middle].GetLocation()-Pose[IndexBase].GetLocation()).GetSafeNormal();
    const FQuat GripToWrist=Pose[Hand].GetRotation().Inverse()*FRotationMatrix::MakeFromXY(Along,Across).ToQuat();
    const FVector FingerTip=Pose[Index].GetLocation()+Along*1.15;
    const FVector TipOnHand=Pose[Hand].InverseTransformPosition(FingerTip);
    const FVector TipOnIndex=Pose[Index].InverseTransformPosition(FingerTip);
    SetMeshSocket(*Mesh,TEXT("RecorderIndexTip"),Ref.GetBoneName(Index),FTransform(TipOnIndex));

    for (const TCHAR* Finger:{TEXT("middle"),TEXT("ring"),TEXT("pinky")})
    {
        const double Flexion[]={23.,68.,42.};
        for (int32 Joint=1;Joint<=3;++Joint)
        {
            const FString Name=FString::Printf(TEXT("f_%s_0%d_R"),Finger,Joint);
            TurnBone(Ref,Fingers,Pose,CityRigBone(Ref,*Name),FQuat(Across,FMath::DegreesToRadians(Flexion[Joint-1])));
            ComponentPose(Ref,Fingers,Pose);
        }
    }

    constexpr int32 Frames=48;
    constexpr int32 TouchFrame=26;
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    for (int32 Frame=0;Frame<=Frames;++Frame)
    {
        const double Time=Frame/30.;
        const double Approach=FMath::SmoothStep(.16,.74,Time);
        const double Retract=FMath::SmoothStep(1.04,1.55,Time);
        const double Reach=Approach*(1.-Retract);
        const double Down=FMath::SmoothStep(.73,.89,Time)*(1.-FMath::SmoothStep(.97,1.08,Time));
        FVector Point=FMath::Lerp(FVector(-34,30,123),FVector(-15,54,153),Reach);
        Point.Z+=4.*FMath::Sin(PI*Reach)-1.35*Down;
        const FVector Direction=FMath::Lerp(FVector(-.18,.96,.10),FVector(-.12,.92,-.32),Reach);
        const FQuat Wrist=FRotationMatrix::MakeFromXY(Direction,FVector(-1.,.04,.10)).ToQuat()*GripToWrist.Inverse();
        TArray<FTransform> Local=Fingers;
        ComponentPose(Ref,Local,Pose);
        CityReach(Ref,Local,Pose,Upper,Elbow,Hand,Point-Wrist.RotateVector(TipOnHand),FVector(-49,10,115),1.);
        RotateWrist(Ref,Local,Pose,Hand,Wrist);
        if (Frame==TouchFrame)
        {
            ComponentPose(Ref,Local,Pose);
            ContactPoint=Pose[Index].TransformPosition(TipOnIndex);
        }
        AppendGesturePose(Local,Tracks);
    }
    return WriteGesture(*Mesh,*Destination,Tracks,Frames);
#else
    return false;
#endif
}

bool UCityCharacterAuthoring::InstallSmokingSlot(UAnimBlueprint* Blueprint)
{
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->TargetSkeleton) return false;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        UAnimGraphNode_Root* Root=nullptr;
        UAnimGraphNode_Slot* Slot=nullptr;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (auto* Output=Cast<UAnimGraphNode_Root>(Node)) Root=Output;
            if (auto* Existing=Cast<UAnimGraphNode_Slot>(Node)) Slot=Existing;
        }
        if (!Root) continue;
        if (!Slot)
        {
            FGraphNodeCreator<UAnimGraphNode_Slot> Creator(*Graph);
            Slot=Creator.CreateNode();
            Slot->Node.SlotName=TEXT("DefaultSlot");
            Slot->NodePosX=Root->NodePosX-290;
            Slot->NodePosY=Root->NodePosY;
            Creator.Finalize();
        }
        Blueprint->TargetSkeleton->RegisterSlotNode(Slot->Node.SlotName);
        UEdGraphPin* Input=Root->FindPin(TEXT("Result"));
        UEdGraphPin* Output=nullptr;
        for (UEdGraphPin* Pin : Slot->Pins)
            if (Pin->Direction==EGPD_Output) {Output=Pin;break;}
        if (!Input || !Output) return false;
        if (!Input->LinkedTo.Contains(Output) && !Graph->GetSchema()->TryCreateConnection(Output,Input)) return false;
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
        return Blueprint->GeneratedClass && Blueprint->Status!=BS_Error;
    }
#endif
    return false;
}
