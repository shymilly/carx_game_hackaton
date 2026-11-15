#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NarrativeInteractionComponent.generated.h"
class UInteractionDocument;
class UDocumentWindow;
class APlayerController;

// Add to an existing report/exit Blueprint; call ActivateInteraction from its existing interaction event.
UCLASS(ClassGroup=(Narrative), meta=(BlueprintSpawnableComponent))
class DOSTOEVSKY_API UNarrativeInteractionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Document") TObjectPtr<UInteractionDocument> Document;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Document") TSubclassOf<UDocumentWindow> WindowClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") bool bExitToStreet = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") TSoftObjectPtr<UWorld> StreetMap;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") FText StreetTitle = NSLOCTEXT("Dostoevsky", "Street", "Улица Американского квартала");
    UFUNCTION(BlueprintCallable, Category="Narrative") bool ActivateInteraction(APlayerController* Player);
};
