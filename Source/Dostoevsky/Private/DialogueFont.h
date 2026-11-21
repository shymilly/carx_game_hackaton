#pragma once

#include "Fonts/CompositeFont.h"
#include "Fonts/SlateFontInfo.h"
#include "Misc/Paths.h"

inline FSlateFontInfo DialogueFont(const TCHAR* Filename, float Size)
{
    const FString Directory = FPaths::ProjectContentDir() / TEXT("UI/Dialogue/Fonts");
    TSharedRef<FCompositeFont> Font = MakeShared<FCompositeFont>();
    Font->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"), Directory / Filename,
        EFontHinting::Default, EFontLoadingPolicy::LazyLoad));
    // Preserve readable names with Cascadia if a character is absent in SOUTHGHETTO.
    Font->FallbackTypeface.Typeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"),
        Directory / TEXT("CascadiaCode-Light.otf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad));
    return FSlateFontInfo(Font, Size);
}
