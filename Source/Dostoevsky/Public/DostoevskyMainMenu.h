#pragma once

#include "Blueprint/UserWidget.h"
#include "GameFramework/GameModeBase.h"
#include "Styling/SlateTypes.h"
#include "Widgets/Input/SButton.h"
#include "DostoevskyMainMenu.generated.h"

class SWidgetSwitcher;
class UTexture2D;

UCLASS()
class DOSTOEVSKY_API UDostoevskyMainMenu : public UUserWidget
{
    GENERATED_BODY()
public:
    void FocusStart();
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void ReleaseSlateResources(bool bReleaseChildren) override;
    virtual FReply NativeOnPreviewKeyDown(const FGeometry& Geometry,const FKeyEvent& Event) override;
    virtual void NativeDestruct() override;
private:
    TSharedRef<SWidget> Button(const FText& Label,bool bPrimary,const FOnClicked& Action);
    TSharedRef<SWidget> Slider(const FText& Label,bool bVolume);
    FReply StartGame();
    FReply ShowSettings();
    FReply Back();
    FReply Quit();
    void CommitSettings();

    UPROPERTY(Transient) TObjectPtr<UTexture2D> Background;
    FSlateBrush BackgroundBrush;
    FButtonStyle PrimaryStyle;
    FButtonStyle SecondaryStyle;
    TSharedPtr<SWidgetSwitcher> Pages;
    TSharedPtr<SWidget> StartButton;
    TSharedPtr<SWidget> VolumeSlider;
    TSharedPtr<SWidget> SettingsButton;
    bool bChangedSettings = false;
    bool bStartingGame = false;
};

UCLASS()
class DOSTOEVSKY_API ADostoevskyMenuGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ADostoevskyMenuGameMode();
    virtual void StartPlay() override;
};
