using UnrealBuildTool;
public class Dostoevsky : ModuleRules
{
    public Dostoevsky(ReadOnlyTargetRules Target) : base(Target)
    {
        if (Target.bBuildEditor) PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "BlueprintGraph", "RenderCore", "SlateNullRenderer", "AnimationCore" });
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "UMG", "InputCore" });
        PrivateDependencyModuleNames.AddRange(new[] { "Slate", "SlateCore", "MoviePlayer" });
    }
}
