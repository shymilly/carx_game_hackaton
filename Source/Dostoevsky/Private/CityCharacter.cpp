#include "CityCharacter.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#if WITH_EDITOR
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
    static constexpr float BlendSeconds = .18f;

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

void RotateWrist(const FReferenceSkeleton& Ref, TArray<FTransform>& Local,
                 TArray<FTransform>& Pose,int32 Wrist,const FQuat& Rotation)
{
    ComponentPose(Ref,Local,Pose);
    Local[Wrist].SetRotation(Pose[Ref.GetParentIndex(Wrist)].GetRotation().Inverse()*Rotation);
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
    const bool bSeatedTalk=Gesture==TEXT("SeatedTalk");
    const bool bTalk=Gesture==TEXT("Talk") || bSeatedTalk;
    const bool bNod=Gesture==TEXT("Nod");
    const bool bArmed=Gesture==TEXT("Armed");
    const bool bShot=Gesture==TEXT("Shot");
    if (!bSmoke && !bTalk && !bNod && !bArmed && !bShot) return false;
    const int32 FrameCount=bSmoke ? 216 : bTalk ? 126 : bNod ? 34 : bShot ? 45 : 72;
    TArray<FGestureKeys> Tracks;
    Tracks.SetNum(Ref.GetNum());
    TArray<FTransform> Local,Pose;
    const int32 Palm=CityRigBone(Ref,TEXT("Palm_R"));
    const int32 Fingers=CityRigBone(Ref,TEXT("Fingers_R"));
    const int32 Thumb=CityRigBone(Ref,TEXT("Thumb2_R"));
    FTransform Grip,Mouth;
    if (bSmoke)
    {
        if (Palm<0 || Fingers<0 || Thumb<0) return false;
        ComponentPose(Ref,Ref.GetRefBonePose(),Pose);
        Grip=CityGrip(Pose,Palm,Fingers,Thumb);
        const double Width=FVector::Dist(Pose[RightUpper].GetLocation(),Pose[LeftUpper].GetLocation());
        const FVector Right=(Pose[RightUpper].GetLocation()-Pose[LeftUpper].GetLocation()).GetSafeNormal2D();
        const FVector Forward=FVector::CrossProduct(Right,FVector::UpVector);
        Mouth=FTransform(FQuat::Identity,Pose[Head].GetLocation()+Forward*Width*.17-FVector::UpVector*Width*.04)
            .GetRelativeTransform(Pose[Head]);
        SetMeshSocket(*Mesh,TEXT("CigaretteGrip"),Ref.GetBoneName(Palm),Grip);
        SetMeshSocket(*Mesh,TEXT("SmokeMouth"),Ref.GetBoneName(Head),Mouth);
    }
    for (int32 Frame=0; Frame<=FrameCount; ++Frame)
    {
        const double Phase=double(Frame)/FrameCount;
        const float T=bSeatedTalk ? Idle->GetPlayLength()*(.37+.26*FMath::Square(FMath::Sin(PI*Phase))) :
            bNod ? 0.f : Idle->GetPlayLength()*Phase;
        CitySamplePose(Ref,Model,T,Local,Pose);
        const FVector Up=FVector::UpVector;
        const FVector Right=(Pose[RightUpper].GetLocation()-Pose[LeftUpper].GetLocation()).GetSafeNormal2D();
        const FVector Forward=FVector::CrossProduct(Right,Up).GetSafeNormal();
        const FVector HeadPosition=Pose[Head].GetLocation();
        const FVector Shoulders=(Pose[RightUpper].GetLocation()+Pose[LeftUpper].GetLocation())*.5;
        const double Width=FVector::Distance(Pose[RightUpper].GetLocation(),Pose[LeftUpper].GetLocation());
        const double Nod=FMath::Sin(PI*Phase)*FMath::Sin(PI*Phase);
        const double Puff=FMath::SmoothStep(.15,.32,Phase)*(1-FMath::SmoothStep(.48,.68,Phase));
        const double Speaking=FMath::Square(FMath::Sin(PI*Phase));
        const double Kick=bShot ? FMath::SmoothStep(.318,.35,Phase)*(1.-FMath::SmoothStep(.36,.56,Phase)) : 0.;
        const double Present=bShot ? FMath::SmoothStep(0.,.22,Phase)*(1.-.65*FMath::SmoothStep(.65,1.,Phase)) : 1.;
        if (bSmoke)
        {
            const FVector Direction=(Forward*.78+Right*.54+Up*.10).GetSafeNormal();
            const FQuat Raised=FRotationMatrix::MakeFromXY(Direction,Up).ToQuat()*Grip.GetRotation().Inverse();
            const FQuat Loose=FRotationMatrix::MakeFromXY((Forward*.8+Right*.28-Up*.25).GetSafeNormal(),Up).ToQuat()
                *Grip.GetRotation().Inverse();
            const FQuat Wrist=FQuat::Slerp(Loose,Raised,Puff);
            const FVector ByLips=Pose[Head].TransformPosition(Mouth.GetLocation())+Direction*Width*.075;
            const FVector AtRest=Shoulders+Forward*Width*.33+Right*Width*.60-Up*Width*.84;
            const FVector SocketLocation=FMath::Lerp(AtRest,ByLips,Puff);
            const FVector Hand=SocketLocation-Wrist.RotateVector(Grip.GetLocation()*Pose[Palm].GetScale3D());
            CityReach(Ref,Local,Pose,RightUpper,RightElbow,Palm,Hand,
                Shoulders+Right*Width*.76+Forward*Width*.55-Up*Width*.76,1.);
            RotateWrist(Ref,Local,Pose,Palm,Wrist);
        }
        else if (bTalk || bArmed || bShot)
        {
            const FVector TalkHand=Shoulders+Forward*Width*(.47+.08*FMath::Sin(4*PI*Phase))+
                Right*Width*.57-Up*Width*(.40+.15*FMath::Cos(4*PI*Phase));
            const FVector Reach=bTalk ? TalkHand :
                Shoulders+Forward*Width*(1.14-.30*Kick)+Right*Width*.14+Up*Width*.25*Kick;
            const FVector Pole=Shoulders+Right*Width*1.1-Up*Width*.9;
            CityReach(Ref,Local,Pose,RightUpper,RightElbow,RightHand,Reach,Pole,
                bTalk ? (bSeatedTalk ? .50 : .72)*Speaking : .94*Present);
            const FVector Other=Shoulders+Forward*Width*(bTalk ? .38 : 1.04-.30*Kick)
                -Right*Width*(bTalk ? .62 : .04)-Up*Width*(bTalk ? .51 : .12-.25*Kick);
            CityReach(Ref,Local,Pose,LeftUpper,LeftElbow,LeftHand,Other,
                Shoulders-Right*Width*1.1-Up*Width*.9,bTalk ? .32*Speaking : .94*Present);
        }
        const double Tilt=bNod ? 12*Nod : bSmoke ? 6*Puff : bTalk ? 5*Speaking*FMath::Sin(6*PI*Phase) : -2;
        FTransform HeadPose=Pose[Head];
        HeadPose.SetRotation(FQuat(Right,FMath::DegreesToRadians(Tilt))*HeadPose.GetRotation());
        Local[Head]=HeadPose.GetRelativeTransform(Pose[Ref.GetParentIndex(Head)]);
        AppendGesturePose(Local,Tracks);
    }
    return WriteGesture(*Mesh,*Destination,Tracks,FrameCount);
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
    for (const TCHAR* Name : {TEXT("f_ring_01_R"),TEXT("f_ring_02_R"),TEXT("f_pinky_01_R"),TEXT("f_pinky_02_R")})
        Curl(Name,29.);
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
