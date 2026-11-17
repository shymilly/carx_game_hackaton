#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Sound/SoundBase.h"
#include "InteractionDocument.generated.h"

class UTexture2D;

UENUM(BlueprintType)
enum class EDocumentLayout : uint8 { Standard, Newspaper, Credits };

USTRUCT(BlueprintType)
struct FNewspaperArticle
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText Section;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText Headline;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText Deck;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(MultiLine=true)) FText Text;
};

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
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") EDocumentLayout Layout = EDocumentLayout::Standard;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") FText Edition;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") TArray<FNewspaperArticle> Articles;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") TObjectPtr<UTexture2D> Illustration;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Document") bool bCropToPortrait = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Audio") TObjectPtr<USoundBase> OpenSound;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Audio") TObjectPtr<USoundBase> Voice;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Audio") TObjectPtr<USoundBase> CloseSound;
};
