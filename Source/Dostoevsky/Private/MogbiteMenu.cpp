#include "MogbiteMenu.h"

#include "Components/AudioComponent.h"
#include "DialoguePanel.h"
#include "DocumentWindow.h"
#include "DostoevskyGameSettings.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Fonts/CompositeFont.h"
#include "GameFramework/GameUserSettings.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "MediaPlayer.h"
#include "MediaTexture.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Paths.h"
#include "Sound/SoundBase.h"
#include "Styling/CoreStyle.h"
#include "TimerManager.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"
#if WITH_EDITOR
#include "Editor.h"
#endif

#define LOCTEXT_NAMESPACE "MogbiteMenu"

namespace
{
constexpr TCHAR RainSection[] = TEXT("Mogbite.Menu");
constexpr TCHAR RainKey[] = TEXT("RainVolume");
constexpr float DesignWidth = 1280.f;
constexpr float DesignHeight = 718.f;

FSlateFontInfo MenuFont(const TCHAR* Filename, float Size)
{
    auto Font = MakeShared<FCompositeFont>();
    Font->DefaultTypeface.Fonts.Emplace(TEXT("Regular"),
        FPaths::ProjectContentDir() / TEXT("UI/MainMenu/Fonts") / Filename,
        EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
    Font->FallbackTypeface.Typeface.Fonts.Emplace(TEXT("Regular"),
        FPaths::ProjectContentDir() / TEXT("UI/Dialogue/Fonts/CascadiaCode-Light.otf"),
        EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
    return FSlateFontInfo(Font, Size);
}

class SMogbiteMenu final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SMogbiteMenu)
        : _Controller(nullptr), _Player(nullptr), _Video(nullptr), _Still(nullptr), _PausePlayer(nullptr) {}
        SLATE_ARGUMENT(AMogbiteMenuController*, Controller)
        SLATE_ARGUMENT(UMediaPlayer*, Player)
        SLATE_ARGUMENT(UMediaTexture*, Video)
        SLATE_ARGUMENT(UTexture2D*, Still)
        SLATE_ARGUMENT(APlayerController*, PausePlayer)
        SLATE_EVENT(FSimpleDelegate, OnResume)
    SLATE_END_ARGS()

    void Construct(const FArguments& Args)
    {
        Controller = Args._Controller;
        bPauseMenu = Args._PausePlayer != nullptr;
        OwningPlayer = bPauseMenu ? Args._PausePlayer : Args._Controller;
        Resume = Args._OnResume;
        Player = Args._Player;
        const auto* DialogueStyle = GetDefault<UDocumentWindow>();
        Paper = DialogueStyle->PanelColor;
        Ink = DialogueStyle->TextColor;
        Accent = DialogueStyle->AccentColor;
        TitleFont = MenuFont(TEXT("Zeitmax.ttf"), 68);
        ButtonFont = MenuFont(TEXT("Jimbi-Regular.ttf"), 27);
        SettingsFont = MenuFont(TEXT("Jimbi-Regular.ttf"), 21);
        if (bPauseMenu)
        {
            BuildPause();
            return;
        }
        SetBrush(StillBrush, Args._Still);
        SetBrush(VideoBrush, Args._Video);

        const TSharedRef<SWidget> Play = PaperButton(LOCTEXT("Play", "ИГРАТЬ"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnPlay), &PlayButton);
        const TSharedRef<SWidget> Settings = PaperButton(LOCTEXT("Settings", "НАСТРОЙКИ"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnSettings), &SettingsButton);
        const TSharedRef<SWidget> Quit = PaperButton(LOCTEXT("Quit", "ВЫХОД"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnQuit));

        ChildSlot
        [
            SNew(SBorder).Padding(0)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.020f, 0.016f, 0.012f))
            [
                SNew(SScaleBox).Stretch(EStretch::ScaleToFit).HAlign(HAlign_Center).VAlign(VAlign_Center)
                [
                    SNew(SBox).WidthOverride(DesignWidth).HeightOverride(DesignHeight)
                    [
                        SNew(SOverlay).Clipping(EWidgetClipping::ClipToBounds)
                        + SOverlay::Slot()
                        [ SNew(SImage).Image(&StillBrush).Visibility(EVisibility::HitTestInvisible) ]
                        + SOverlay::Slot()
                        [
                            SNew(SImage).Image(&VideoBrush).Visibility_Lambda([this]
                            {
                                return Player.IsValid() && Player->IsReady() && Player->GetVideoTrackDimensions(INDEX_NONE, INDEX_NONE).X > 0
                                    ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
                            })
                        ]
                        + SOverlay::Slot().Padding(26, 20)
                        [
                            SNew(SDialoguePanel).Fill(FLinearColor::Transparent).Outline(Accent.CopyWithNewOpacity(0.58f))
                            .Radius(22).Padding(0).Visibility(EVisibility::HitTestInvisible)
                        ]
                        + SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(67, 76, 0, 0)
                        [
                            SNew(SBox).WidthOverride(420)
                            [
                                SNew(SVerticalBox)
                                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 0, 0, 25)
                                [
                                    SNew(STextBlock).Text(LOCTEXT("Title", "fogbite")).Font(TitleFont)
                                    .ColorAndOpacity(Paper).ShadowOffset(FVector2D(2, 4))
                                    .ShadowColorAndOpacity(FLinearColor(0, 0, 0, .85f))
                                ]
                                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                                [
                                    SAssignNew(Pages, SWidgetSwitcher)
                                    + SWidgetSwitcher::Slot()
                                    [
                                        SNew(SBox).WidthOverride(270).HAlign(HAlign_Fill)
                                        [
                                            SNew(SVerticalBox)
                                            + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 14)[ Play ]
                                            + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 14)[ Settings ]
                                            + SVerticalBox::Slot().AutoHeight()[ Quit ]
                                        ]
                                    ]
                                    + SWidgetSwitcher::Slot()[ BuildSettings() ]
                                    + SWidgetSwitcher::Slot()
                                    [
                                        SNew(SDialoguePanel).Fill(Paper).Outline(Accent).Radius(16).Padding(FMargin(24, 14))
                                        [ SNew(STextBlock).Text(LOCTEXT("Loading", "ЗАГРУЗКА…")).Font(ButtonFont).ColorAndOpacity(Ink) ]
                                    ]
                                ]
                            ]
                        ]
                    ]
                ]
            ]
        ];
    }

    TSharedPtr<SWidget> GetInitialFocus() const { return PlayButton; }

    virtual FReply OnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override
    {
        const FKey Key = Event.GetKey();
        if (bPauseMenu && Pages->GetActiveWidgetIndex() == 0 && (Key == EKeys::Down || Key == EKeys::Up || Key == EKeys::Tab))
        {
            const TSharedPtr<SButton> Buttons[] = { PlayButton, SettingsButton, PauseQuitButton };
            const int32 Focused = PauseQuitButton->HasAnyUserFocus() ? 2 : SettingsButton->HasAnyUserFocus() ? 1 : 0;
            const int32 Step = Key == EKeys::Up || (Key == EKeys::Tab && Event.IsShiftDown()) ? 2 : 1;
            return FReply::Handled().SetUserFocus(Buttons[(Focused+Step)%3].ToSharedRef(), EFocusCause::Navigation);
        }
        return SCompoundWidget::OnPreviewKeyDown(Geometry, Event);
    }

    virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override
    {
        if (Event.GetKey() == EKeys::Escape && !Event.IsRepeat())
        {
            if (Pages->GetActiveWidgetIndex() == 1) return OnBack();
            if (bPauseMenu) return OnResumeGame();
        }
        return SCompoundWidget::OnKeyDown(Geometry, Event);
    }

private:
    void BuildPause()
    {
        ChildSlot
        [
            SNew(SBorder).Padding(20)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.012f, 0.010f, 0.007f, .72f))
            .HAlign(HAlign_Center).VAlign(VAlign_Center)
            [
                SNew(SScaleBox).Stretch(EStretch::ScaleToFit).StretchDirection(EStretchDirection::DownOnly)
                [
                    SAssignNew(Pages, SWidgetSwitcher)
                    + SWidgetSwitcher::Slot()
                    [
                        SNew(SBox).WidthOverride(325)
                        [
                            SNew(SDialoguePanel).Fill(Paper).Outline(Accent).Radius(20).Padding(FMargin(26, 21))
                            [
                                SNew(SVerticalBox)
                                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 0, 0, 14)
                                [ SNew(STextBlock).Text(LOCTEXT("Pause", "ПАУЗА")).Font(ButtonFont).ColorAndOpacity(Ink) ]
                                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 9)
                                [ PaperButton(LOCTEXT("Resume", "ПРОДОЛЖИТЬ"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnResumeGame), &PlayButton, true) ]
                                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 9)
                                [ PaperButton(LOCTEXT("Settings", "НАСТРОЙКИ"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnSettings), &SettingsButton, true) ]
                                + SVerticalBox::Slot().AutoHeight()
                                [ PaperButton(LOCTEXT("Quit", "ВЫХОД"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnQuit), &PauseQuitButton, true) ]
                            ]
                        ]
                    ]
                    + SWidgetSwitcher::Slot()[ BuildSettings() ]
                ]
            ]
        ];
    }

    FReply OnResumeGame()
    {
        Resume.ExecuteIfBound();
        return FReply::Handled();
    }

    static void SetBrush(FSlateBrush& Brush, UTexture* Texture)
    {
        Brush.SetResourceObject(Texture);
        Brush.SetImageSize(FVector2D(DesignWidth, DesignHeight));
        Brush.DrawAs = Texture ? ESlateBrushDrawType::Image : ESlateBrushDrawType::NoDrawType;
    }

    TSharedRef<SWidget> PaperButton(const TAttribute<FText>& Text, FOnClicked Click,
        TSharedPtr<SButton>* OutButton = nullptr, bool bCompact = false)
    {
        const TSharedRef<SButton> Button = SNew(SButton)
            .ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
            .HAlign(HAlign_Center).VAlign(VAlign_Center).ContentPadding(0)
            .OnClicked(MoveTemp(Click))
            [ SNew(STextBlock).Text(Text).Font(bCompact ? SettingsFont : ButtonFont).ColorAndOpacity(Ink) ];
        if (OutButton) *OutButton = Button;
        const TWeakPtr<SButton> WeakButton = Button;
        return SNew(SBox).HeightOverride(bCompact ? 46 : 62)
        [
            SNew(SDialoguePanel).Radius(14).Padding(0).Outline(Accent)
            .Fill_Lambda([WeakButton, Color = Paper, Highlight = Accent]
            {
                const auto Pinned = WeakButton.Pin();
                const float Mix = Pinned && Pinned->IsPressed() ? .72f :
                    (Pinned && (Pinned->IsHovered() || Pinned->HasAnyUserFocus()) ? .38f : 0.f);
                return FMath::Lerp(Color, Highlight, Mix);
            })
            [ Button ]
        ];
    }

    TSharedRef<SWidget> BuildSettings()
    {
        return SNew(SBox).WidthOverride(360)
        [
            SNew(SDialoguePanel).Fill(Paper).Outline(Accent).Radius(20).Padding(FMargin(23, 18))
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 1, 0, 14)
                [ SNew(STextBlock).Text(LOCTEXT("Settings", "НАСТРОЙКИ")).Font(ButtonFont).ColorAndOpacity(Ink) ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 9)
                [ PaperButton(TAttribute<FText>::CreateLambda([this] { return GraphicsLabel(); }),
                    FOnClicked::CreateLambda([this] { Quality = (Quality + 1) % 5; return FReply::Handled(); }), &GraphicsButton, true) ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 13)
                [ PaperButton(TAttribute<FText>::CreateLambda([this] { return WindowLabel(); }),
                    FOnClicked::CreateLambda([this] { Window = (Window + 1) % 3; return FReply::Handled(); }), nullptr, true) ]
                + SVerticalBox::Slot().AutoHeight().Padding(3, 0, 3, 7)
                  [ SettingsSlider(LOCTEXT("Volume", "Общая громкость"), &SMogbiteMenu::PendingVolume) ]
                + SVerticalBox::Slot().AutoHeight().Padding(3, 0, 3, 7)
                  [ SettingsSlider(LOCTEXT("Brightness", "Яркость"), &SMogbiteMenu::PendingBrightness) ]
                + SVerticalBox::Slot().AutoHeight().Padding(3, 0, 3, 11)
                  [
                      SNew(SBox).Visibility(bPauseMenu ? EVisibility::Collapsed : EVisibility::Visible)
                      [ SettingsSlider(LOCTEXT("RainVolume", "Дождь в меню"), &SMogbiteMenu::PendingRain) ]
                  ]
                + SVerticalBox::Slot().AutoHeight()
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().FillWidth(1).Padding(0, 0, 8, 0)
                    [ PaperButton(LOCTEXT("Apply", "ПРИМЕНИТЬ"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnApply), nullptr, true) ]
                    + SHorizontalBox::Slot().FillWidth(1)
                    [ PaperButton(LOCTEXT("Back", "НАЗАД"), FOnClicked::CreateSP(this, &SMogbiteMenu::OnBack), nullptr, true) ]
                ]
            ]
        ];
    }

    TSharedRef<SWidget> SettingsSlider(const FText& Label, float SMogbiteMenu::* Value)
    {
        const FLinearColor ControlColor(.25f, .16f, .05f);
        return SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1.65f).VAlign(VAlign_Center).Padding(0, 0, 6, 0)
              [SNew(STextBlock).Text(Label).Font(SettingsFont).ColorAndOpacity(Ink)]
            + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
            [
                SNew(SSlider).Value_Lambda([this, Value] { return this->*Value; }).StepSize(.05f)
                .SliderBarColor(ControlColor).SliderHandleColor(ControlColor)
                .OnValueChanged_Lambda([this, Value](float NewValue)
                {
                    this->*Value = NewValue;
                    if (Value == &SMogbiteMenu::PendingVolume)
                    {
                        if (const auto* Settings = UDostoevskyGameSettings::Get()) Settings->PreviewMasterVolume(NewValue);
                    }
                    if (Value == &SMogbiteMenu::PendingRain && Controller.IsValid()) Controller->SetRainVolume(NewValue);
                })
            ];
    }

    FText GraphicsLabel() const
    {
        const FText Names[] = { LOCTEXT("Low", "Низкая"), LOCTEXT("Medium", "Средняя"),
            LOCTEXT("High", "Высокая"), LOCTEXT("Epic", "Эпическая"), LOCTEXT("Cinematic", "Кино") };
        const FText Value = Quality == INDEX_NONE ? LOCTEXT("Custom", "Своя") : Names[Quality];
        return FText::Format(LOCTEXT("Graphics", "Графика: {0}"), Value);
    }

    FText WindowLabel() const
    {
        const FText Names[] = { LOCTEXT("Fullscreen", "Полный экран"),
            LOCTEXT("Borderless", "Без рамки"), LOCTEXT("Windowed", "В окне") };
        return Names[Window];
    }

    FReply OnPlay()
    {
        if (Controller.IsValid())
        {
            Pages->SetActiveWidgetIndex(2);
            Controller->PlayGame();
        }
        return FReply::Handled();
    }

    FReply OnSettings()
    {
        if (auto* Settings = GEngine->GetGameUserSettings())
        {
            Quality = FMath::Clamp(Settings->GetOverallScalabilityLevel(), INDEX_NONE, 4);
            Window = FMath::Clamp(static_cast<int32>(Settings->GetFullscreenMode()), 0, 2);
        }
        if (const auto* Settings = UDostoevskyGameSettings::Get())
        {
            PendingVolume = Settings->GetMasterVolume();
            PendingBrightness = Settings->GetSceneBrightness();
        }
        OriginalRain = PendingRain = Controller.IsValid() ? Controller->GetRainVolume() : .45f;
        Pages->SetActiveWidgetIndex(1);
        return FReply::Handled().SetUserFocus(GraphicsButton.ToSharedRef());
    }

    FReply OnApply()
    {
        if (auto* Settings = UDostoevskyGameSettings::Get())
        {
            Settings->SetMasterVolume(PendingVolume);
            Settings->SetSceneBrightness(PendingBrightness);
        }
        if (auto* Settings = GEngine->GetGameUserSettings())
        {
            if (Quality != INDEX_NONE && Quality != Settings->GetOverallScalabilityLevel()) Settings->SetOverallScalabilityLevel(Quality);
            // The editor owns the PIE window. Only standalone and packaged games can change its mode.
            if (OwningPlayer.IsValid() && OwningPlayer->GetWorld()->WorldType != EWorldType::PIE)
                Settings->SetFullscreenMode(static_cast<EWindowMode::Type>(Window));
            Settings->ApplySettings(false);
        }
        if (Controller.IsValid()) Controller->SaveRainVolume();
        OriginalRain = PendingRain;
        return OnBack();
    }

    FReply OnBack()
    {
        if (const auto* Settings = UDostoevskyGameSettings::Get()) Settings->PreviewMasterVolume(Settings->GetMasterVolume());
        if (Controller.IsValid()) Controller->SetRainVolume(OriginalRain);
        Pages->SetActiveWidgetIndex(0);
        return FReply::Handled().SetUserFocus(SettingsButton.ToSharedRef());
    }

    FReply OnQuit()
    {
        APlayerController* LocalPlayer = OwningPlayer.Get();
        if (!LocalPlayer) return FReply::Handled();
#if WITH_EDITOR
        if (bPauseMenu && GEditor && LocalPlayer->GetWorld()->WorldType == EWorldType::PIE)
        {
            UE_LOG(LogTemp, Verbose, TEXT("Pause menu requests the end of Play in Editor"));
            GEditor->RequestEndPlayMap();
            return FReply::Handled();
        }
#endif
        UKismetSystemLibrary::QuitGame(LocalPlayer, LocalPlayer, EQuitPreference::Quit, false);
        return FReply::Handled();
    }

    TWeakObjectPtr<AMogbiteMenuController> Controller;
    TWeakObjectPtr<APlayerController> OwningPlayer;
    FSimpleDelegate Resume;
    bool bPauseMenu = false;
    TWeakObjectPtr<UMediaPlayer> Player;
    TSharedPtr<SWidgetSwitcher> Pages;
    TSharedPtr<SButton> PlayButton;
    TSharedPtr<SButton> SettingsButton;
    TSharedPtr<SButton> GraphicsButton;
    TSharedPtr<SButton> PauseQuitButton;
    FSlateBrush StillBrush;
    FSlateBrush VideoBrush;
    FSlateFontInfo TitleFont;
    FSlateFontInfo ButtonFont;
    FSlateFontInfo SettingsFont;
    FLinearColor Paper;
    FLinearColor Ink;
    FLinearColor Accent;
    int32 Quality = 2;
    int32 Window = 1;
    float OriginalRain = .45f;
    float PendingRain = .45f;
    float PendingVolume = 1.f;
    float PendingBrightness = .5f;
};
}

TSharedRef<SWidget> CreateMogbitePauseMenu(APlayerController* Player, FSimpleDelegate Resume,
    TSharedPtr<SWidget>& InitialFocus)
{
    const auto Widget = SNew(SMogbiteMenu).PausePlayer(Player).OnResume(MoveTemp(Resume));
    InitialFocus = Widget->GetInitialFocus();
    return Widget;
}

AMogbiteMenuMode::AMogbiteMenuMode()
{
    DefaultPawnClass = nullptr;
    PlayerControllerClass = AMogbiteMenuController::StaticClass();
}

void AMogbiteMenuController::BeginPlay()
{
    Super::BeginPlay();
    UGameViewportClient* Viewport = GetWorld()->GetGameViewport();
    if (!IsLocalController() || !Viewport) return;
    if (const auto* Settings = UDostoevskyGameSettings::Get()) Settings->ApplyPresentationSettings();

    GConfig->GetFloat(RainSection, RainKey, RainVolume, GGameUserSettingsIni);
    RainVolume = FMath::Clamp(RainVolume, 0.f, 1.f);
    if (USoundBase* Sound = LoadObject<USoundBase>(nullptr, TEXT("/Game/UI/MainMenu/S_MenuRain.S_MenuRain")))
    {
        RainAudio = UGameplayStatics::SpawnSound2D(this, Sound, RainVolume);
    }

    StillImage = LoadObject<UTexture2D>(nullptr, TEXT("/Game/UI/MainMenu/T_MenuStill.T_MenuStill"));
    VideoPlayer = NewObject<UMediaPlayer>(this);
    VideoPlayer->SetLooping(true);
    VideoTexture = NewObject<UMediaTexture>(this);
    VideoTexture->SetMediaPlayer(VideoPlayer);
    VideoTexture->UpdateResource();
    const FString Movie = FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir() / TEXT("Movies/Rain_glass_and_smoke.mp4"));
    if (!VideoPlayer->OpenFile(Movie)) UE_LOG(LogTemp, Warning, TEXT("Mogbite menu: using the still background."));

    const auto Screen = SNew(SMogbiteMenu).Controller(this).Player(VideoPlayer).Video(VideoTexture).Still(StillImage);
    Menu = Screen;
    Viewport->AddViewportWidgetContent(Screen, 30);
    bShowMouseCursor = true;
    FInputModeUIOnly Input;
    Input.SetWidgetToFocus(Screen->GetInitialFocus());
    SetInputMode(Input);
}

void AMogbiteMenuController::EndPlay(const EEndPlayReason::Type Reason)
{
    GetWorldTimerManager().ClearTimer(StartTimer);
    if (Menu.IsValid())
    {
        if (UGameViewportClient* Viewport = GetWorld()->GetGameViewport()) Viewport->RemoveViewportWidgetContent(Menu.ToSharedRef());
        Menu.Reset();
        bShowMouseCursor = false;
        SetInputMode(FInputModeGameOnly());
    }
    if (RainAudio) RainAudio->Stop();
    if (VideoPlayer) VideoPlayer->Close();
    Super::EndPlay(Reason);
}

void AMogbiteMenuController::PlayGame()
{
    if (bStarting) return;
    bStarting = true;
    if (RainAudio) RainAudio->FadeOut(.15f, 0.f);
    GetWorldTimerManager().SetTimer(StartTimer, this, &ThisClass::OpenApartment, .16f, false);
}

void AMogbiteMenuController::OpenApartment()
{
    UGameplayStatics::OpenLevel(this, TEXT("/Game/Locations/L_DimaApartmentInterior"));
}

void AMogbiteMenuController::SetRainVolume(float Volume)
{
    RainVolume = FMath::Clamp(Volume, 0.f, 1.f);
    if (RainAudio) RainAudio->SetVolumeMultiplier(RainVolume);
}

void AMogbiteMenuController::SaveRainVolume()
{
    GConfig->SetFloat(RainSection, RainKey, RainVolume, GGameUserSettingsIni);
    GConfig->Flush(false, GGameUserSettingsIni);
}

#undef LOCTEXT_NAMESPACE
