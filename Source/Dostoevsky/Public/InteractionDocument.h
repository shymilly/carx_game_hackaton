#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Sound/SoundBase.h"
#include "InteractionDocument.generated.h"

// One asset per report, note or dialogue page. No story text is hardcoded.
UCLASS(BlueprintType)
class DOSTOEVSKY_API UInteractionDocument : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") FText Title;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") FText Speaker;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document", meta=(MultiLine=true)) FText Body;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") FText CloseLabel;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Audio") TObjectPtr<USoundBase> OpenSound;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Audio") TObjectPtr<USoundBase> Voice;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Audio") TObjectPtr<USoundBase> CloseSound;
};
