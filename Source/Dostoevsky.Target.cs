using UnrealBuildTool;
public class DostoevskyTarget : TargetRules
{
    public DostoevskyTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("Dostoevsky");
    }
}
