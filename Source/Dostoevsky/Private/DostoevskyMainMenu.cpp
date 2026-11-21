#include "DostoevskyMainMenu.h"

#include "DostoevskyGameSettings.h"
#include "Brushes/SlateImageBrush.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Engine/Texture2D.h"
#include "Fonts/CompositeFont.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/Paths.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "DostoevskyMainMenu"

namespace
{
constexpr TCHAR CoverAsset[]=TEXT("/Game/UI/Menu/T_MainMenuBrighton.T_MainMenuBrighton");
const FLinearColor Parchment=FLinearColor::FromSRGBColor(FColor(233,204,155));
const FLinearColor Cream=FLinearColor::FromSRGBColor(FColor(249,236,213));
const FLinearColor Ink=FLinearColor::FromSRGBColor(FColor(28,22,19));

FSlateFontInfo MenuFont(bool bTitle,float Size)
{
    const TCHAR* File=bTitle ? TEXT("Podkova-Bold.ttf") : TEXT("CascadiaCode-Light.otf");
    TSharedRef<FCompositeFont> Font=MakeShared<FCompositeFont>();
    Font->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"),FPaths::ProjectContentDir()/TEXT("UI/Dialogue/Fonts")/File,
        EFontHinting::Default,EFontLoadingPolicy::LazyLoad));
    return FSlateFontInfo(Font,Size);
}

float SettingValue(bool bVolume)
{
    const UDostoevskyGameSettings* Settings=UDostoevskyGameSettings::Get();
    if (!Settings) return bVolume ? 1.f : .5f;
    return bVolume ? Settings->GetMasterVolume() : Settings->GetSceneBrightness();
}

FButtonStyle BuildButtonStyle(bool bPrimary)
{
    const FLinearColor Bronze=FLinearColor::FromSRGBColor(FColor(132,104,75));
    const FLinearColor Face=bPrimary ? Parchment : FLinearColor(.028f,.020f,.017f,.95f);
    const FLinearColor Hover=bPrimary ? Cream : FLinearColor(.11f,.073f,.046f,1.f);
    const FLinearColor Pressed=bPrimary ? Parchment*.82f : FLinearColor(.065f,.045f,.036f,1.f);
    FButtonStyle Result;
    Result.SetNormal(FSlateRoundedBoxBrush(Face,4.f,Bronze,1.f));
    Result.SetHovered(FSlateRoundedBoxBrush(Hover,4.f,Parchment,1.f));
    Result.SetPressed(FSlateRoundedBoxBrush(Pressed,4.f,Parchment,1.f));
    Result.SetNormalPadding(FMargin(18,9));
    Result.SetPressedPadding(FMargin(18,10,18,8));
    return Result;
}

class SMenuShade : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SMenuShade) {} SLATE_END_ARGS()
    void Construct(const FArguments&) { SetVisibility(EVisibility::HitTestInvisible); }
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }
    virtual int32 OnPaint(const FPaintArgs&,const FGeometry& Geometry,const FSlateRect&,
        FSlateWindowElementList& Elements,int32 Layer,const FWidgetStyle&,bool) const override
    {
        const float Width=Geometry.GetLocalSize().X;
        const TArray<FSlateGradientStop> Stops{
            {FVector2f(0,0),FLinearColor(.008f,.006f,.005f,.98f)},
            {FVector2f(Width*.32f,0),FLinearColor(.009f,.007f,.005f,.94f)},
            {FVector2f(Width*.62f,0),FLinearColor(.010f,.008f,.006f,.16f)},
            {FVector2f(Width,0),FLinearColor(.009f,.007f,.005f,.06f)}
        };
        FSlateDrawElement::MakeGradient(Elements,Layer,Geometry.ToPaintGeometry(),Stops,Orient_Vertical);
        return Layer;
    }
};
}

ADostoevskyMenuGameMode::ADostoevskyMenuGameMode()
{
    DefaultPawnClass=nullptr;
    HUDClass=nullptr;
}

void ADostoevskyMenuGameMode::StartPlay()
{
    Super::StartPlay();
    APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    if (!Player || !Player->IsLocalController()) return;
    if (const UDostoevskyGameSettings* Settings=UDostoevskyGameSettings::Get())
        Settings->ApplyToWorld(GetWorld());
    if (UDostoevskyMainMenu* Menu=CreateWidget<UDostoevskyMainMenu>(Player,UDostoevskyMainMenu::StaticClass()))
    {
        Menu->AddToViewport(80);
        Menu->FocusStart();
    }
}

TSharedRef<SWidget> UDostoevskyMainMenu::Button(const FText& Label,bool bPrimary,const FOnClicked& Action)
{
    return SNew(SBox).HeightOverride(56)
        [SNew(SButton)
            .ButtonStyle(bPrimary ? &PrimaryStyle : &SecondaryStyle)
            .HAlign(HAlign_Left).VAlign(VAlign_Center).OnClicked(Action)
            [SNew(STextBlock).Text(Label).Font(MenuFont(false,19)).ColorAndOpacity(bPrimary ? Ink : Cream)]];
}

TSharedRef<SWidget> UDostoevskyMainMenu::Slider(const FText& Label,bool bVolume)
{
    TSharedRef<SSlider> Control=SNew(SSlider)
        .Value_Lambda([bVolume]() { return SettingValue(bVolume); })
        .IndentHandle(false).StepSize(.02f).RequiresControllerLock(false)
        .SliderBarColor(FLinearColor(.29f,.24f,.18f,1.f)).SliderHandleColor(Parchment)
        .OnValueChanged_Lambda([this,bVolume](float Value)
        {
            UDostoevskyGameSettings* Settings=UDostoevskyGameSettings::Get();
            if (!Settings) return;
            if (bVolume) Settings->SetMasterVolume(Value,GetWorld());
            else Settings->SetSceneBrightness(Value);
            bChangedSettings=true;
        })
        .OnMouseCaptureEnd_UObject(this,&UDostoevskyMainMenu::CommitSettings)
        .OnControllerCaptureEnd_UObject(this,&UDostoevskyMainMenu::CommitSettings);
    if (bVolume) VolumeSlider=Control;
    return SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,11)
        [SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1)
             [SNew(STextBlock).Text(Label).Font(MenuFont(false,18)).ColorAndOpacity(Cream)]
            + SHorizontalBox::Slot().AutoWidth()
             [SNew(STextBlock).Font(MenuFont(false,17)).ColorAndOpacity(Parchment)
              .Text_Lambda([bVolume]() { return FText::AsPercent(SettingValue(bVolume)); })]]
        + SVerticalBox::Slot().AutoHeight()
        [SNew(SBox).HeightOverride(22)[Control]];
}

TSharedRef<SWidget> UDostoevskyMainMenu::RebuildWidget()
{
    SetIsFocusable(true);
    Background=LoadObject<UTexture2D>(nullptr,CoverAsset);
    if (Background)
        BackgroundBrush=FSlateImageBrush(Background,FVector2D(Background->GetSizeX(),Background->GetSizeY()));
    PrimaryStyle=BuildButtonStyle(true);
    SecondaryStyle=BuildButtonStyle(false);

    StartButton=Button(LOCTEXT("StartGame","Начать игру"),true,FOnClicked::CreateUObject(this,&UDostoevskyMainMenu::StartGame));
    SettingsButton=Button(LOCTEXT("SettingsAction","Настройки"),false,FOnClicked::CreateUObject(this,&UDostoevskyMainMenu::ShowSettings));
    TSharedRef<SWidget> QuitButton=Button(LOCTEXT("Quit","Выйти"),false,FOnClicked::CreateUObject(this,&UDostoevskyMainMenu::Quit));
    TSharedRef<SWidget> BackButton=Button(LOCTEXT("Back","Назад"),false,FOnClicked::CreateUObject(this,&UDostoevskyMainMenu::Back));
    Pages=SNew(SWidgetSwitcher)
        + SWidgetSwitcher::Slot()
        [SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,33)
             [SNew(STextBlock).Text(LOCTEXT("Title","Отголоски\nпрошлого")).Font(MenuFont(true,48)).ColorAndOpacity(Cream).LineHeightPercentage(.94f)]
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,10)[StartButton.ToSharedRef()]
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,10)[SettingsButton.ToSharedRef()]
            + SVerticalBox::Slot().AutoHeight()[QuitButton]]
        + SWidgetSwitcher::Slot()
        [SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,35)
             [SNew(STextBlock).Text(LOCTEXT("SettingsTitle","Настройки")).Font(MenuFont(true,48)).ColorAndOpacity(Cream)]
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,24)[Slider(LOCTEXT("Volume","Громкость"),true)]
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,37)[Slider(LOCTEXT("Brightness","Яркость"),false)]
            + SVerticalBox::Slot().AutoHeight()[BackButton]];

    return SNew(SOverlay)
        + SOverlay::Slot()
        [SNew(SScaleBox).Stretch(EStretch::ScaleToFill).Clipping(EWidgetClipping::ClipToBounds)
            [SNew(SImage).Image(&BackgroundBrush).ColorAndOpacity_Lambda([]()
                { const float Tint=FMath::Lerp(.48f,1.f,SettingValue(false)); return FLinearColor(Tint,Tint,Tint,1.f); })]]
        + SOverlay::Slot()[SNew(SMenuShade)]
        + SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Center).Padding(68,28,28,28)
        [SNew(SScaleBox).Stretch(EStretch::ScaleToFit).StretchDirection(EStretchDirection::DownOnly)
            [SNew(SBox).WidthOverride(365)[Pages.ToSharedRef()]]];
}

void UDostoevskyMainMenu::FocusStart()
{
    if (APlayerController* Player=GetOwningPlayer())
    {
        FInputModeUIOnly Mode;
        // The clickable button is the child of an SBox used to size the row.
        Mode.SetWidgetToFocus(StartButton->GetChildren()->GetChildAt(0));
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Player->SetInputMode(Mode);
        Player->bShowMouseCursor=true;
    }
}

FReply UDostoevskyMainMenu::StartGame()
{
    if (APlayerController* Player=GetOwningPlayer(); Player && !bStartingGame)
    {
        bStartingGame=true;
        CommitSettings();
        Player->bShowMouseCursor=false;
        Player->SetInputMode(FInputModeGameOnly());
        RemoveFromParent();
        UGameplayStatics::OpenLevel(Player,TEXT("/Game/Locations/L_DimaApartmentInterior"));
    }
    return FReply::Handled();
}

FReply UDostoevskyMainMenu::ShowSettings()
{
    Pages->SetActiveWidgetIndex(1);
    return FReply::Handled().SetUserFocus(VolumeSlider.ToSharedRef(),EFocusCause::SetDirectly);
}

FReply UDostoevskyMainMenu::Back()
{
    CommitSettings();
    Pages->SetActiveWidgetIndex(0);
    return FReply::Handled().SetUserFocus(SettingsButton->GetChildren()->GetChildAt(0),EFocusCause::SetDirectly);
}

FReply UDostoevskyMainMenu::Quit()
{
    CommitSettings();
    UKismetSystemLibrary::QuitGame(this,GetOwningPlayer(),EQuitPreference::Quit,false);
    return FReply::Handled();
}

void UDostoevskyMainMenu::CommitSettings()
{
    if (!bChangedSettings) return;
    if (UDostoevskyGameSettings* Settings=UDostoevskyGameSettings::Get()) Settings->SaveSettings();
    bChangedSettings=false;
}

FReply UDostoevskyMainMenu::NativeOnPreviewKeyDown(const FGeometry& Geometry,const FKeyEvent& Event)
{
    if (Event.GetKey()==EKeys::Escape && Pages && Pages->GetActiveWidgetIndex()==1) return Back();
    return Super::NativeOnPreviewKeyDown(Geometry,Event);
}

void UDostoevskyMainMenu::NativeDestruct()
{
    CommitSettings();
    Super::NativeDestruct();
}

void UDostoevskyMainMenu::ReleaseSlateResources(bool bReleaseChildren)
{
    Super::ReleaseSlateResources(bReleaseChildren);
    Pages.Reset();
    StartButton.Reset();
    VolumeSlider.Reset();
    SettingsButton.Reset();
}

#undef LOCTEXT_NAMESPACE
