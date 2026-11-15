using UnrealBuildTool;
public class DostoevskyEditorTarget : TargetRules
{
    public DostoevskyEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("Dostoevsky");
    }
}
