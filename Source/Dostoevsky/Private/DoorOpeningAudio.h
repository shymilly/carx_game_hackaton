#pragma once

#include "CoreMinimal.h"

class AActor;

enum class EDoorOpeningSound : uint8
{
    Wood,
    Entry,
    Fridge
};

namespace DoorOpeningAudio
{
void Play(const AActor* Door, EDoorOpeningSound Kind=EDoorOpeningSound::Wood);
}
