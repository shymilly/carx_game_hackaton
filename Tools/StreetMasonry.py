"""Keep a common brick size on legacy trim, facades and factory surfaces."""
import unreal as ue

from BrightonStreetDetails import expression
from BrightonUpgrade import LIB, P, color, connect, constant, node, output, save, wet_value

BRICK_WIDTH_CM = 22.5
COURSE_HEIGHT_CM = 7.5

STREET = "/Game/Prologue/Street"
REFINEMENT = "/Game/StreetRefinement"
ART = "/Game/StreetArtPass/Materials"


def masonry(material, albedo, normal, courses, tint, roughness):
    return tiled_surface(material, albedo, normal, (4 * BRICK_WIDTH_CM, courses * COURSE_HEIGHT_CM), tint, roughness)


def tiled_surface(material, albedo, normal, span, tint, roughness, *, weather=None, siding=False, pbr=None):
    """Project the source tile in centimeters without inheriting an actor's nonuniform scale."""
    mat = ue.load_asset(material)
    base_texture = ue.load_asset(albedo)
    assert mat and base_texture, (material, albedo)
    LIB.delete_all_material_expressions(mat)
    mat.set_editor_properties(dict(tangent_space_normal=False,
        shading_model=ue.MaterialShadingModel.MSM_DEFAULT_LIT,used_with_instanced_static_meshes=True))
    world = node(mat,ue.MaterialExpressionWorldPosition)
    camera = node(mat,ue.MaterialExpressionCameraVectorWS)
    outward = expression(mat,{"World":world,"View":camera}, """
        float3 crossNormal = cross(ddx(World.xyz),ddy(World.xyz));
        float3 faceNormal = normalize(crossNormal + float3(1e-9,1e-9,1e-9));
        return dot(faceNormal,View) >= 0 ? faceNormal : -faceNormal;""",ue.CustomMaterialOutputType.CMOT_FLOAT3)
    across = expression(mat,{"Face":outward}, """
        return abs(Face.z)<.8 ? normalize(cross(float3(0,0,1),Face)) : float3(1,0,0);
        """,ue.CustomMaterialOutputType.CMOT_FLOAT3)
    width, height = span
    uv = expression(mat,{"World":world,"Face":outward,"Across":across}, f"""
        float3 down = cross(Across,Face);
        return float2(dot(World.xyz,Across),dot(World.xyz,down)) / float2({width:.4f},{height:.4f});
        """,ue.CustomMaterialOutputType.CMOT_FLOAT2)
    uv.set_editor_property("description","Surface tile in world centimeters")
    sample = node(mat,ue.MaterialExpressionTextureSample,texture=base_texture)
    connect(uv,sample)
    shade = node(mat,ue.MaterialExpressionMultiply)
    connect(sample,shade,"A","RGB")
    connect(color(mat,tint),shade,"B")
    base_color = shade
    surface_roughness = constant(mat,roughness)
    if siding:
        ribbed = expression(mat,{"World":world,"Finish":base_color}, """
            float band = frac(World.z/15.5);
            float edge = max(.024, fwidth(World.z/15.5));
            return Finish * lerp(.79,1.0,smoothstep(.028-edge,.10+edge,band));""",
            ue.CustomMaterialOutputType.CMOT_FLOAT3)
        base_color = ribbed
    if weather:
        wet = wet_value(mat,weather)
        base_color = expression(mat,{"Finish":base_color,"Wet":wet},
            "return Finish * (1 - .29 * Wet);",ue.CustomMaterialOutputType.CMOT_FLOAT3)
        surface_roughness = expression(mat,{"World":world,"Wet":wet,"Dry":surface_roughness}, """
            float2 p = World.xy*.006;
            float mask = sin(p.x+.8*sin(p.y*1.7))*sin(p.y*1.24-.4*cos(p.x*1.8));
            return lerp(Dry,lerp(.30,.13,smoothstep(.05,.61,mask)),Wet);""",
            ue.CustomMaterialOutputType.CMOT_FLOAT1)
    if pbr:
        for channel, texture_path in pbr.items():
            texture = ue.load_asset(texture_path)
            assert texture,texture_path
            scalar = node(mat,ue.MaterialExpressionTextureSample,texture=texture,
                          sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
            connect(uv,scalar)
            if channel == P.MP_ROUGHNESS:
                surface_roughness = expression(mat,{"R":scalar},"return R.r;",ue.CustomMaterialOutputType.CMOT_FLOAT1)
            else:
                output(scalar,mat,channel,"R")
    output(base_color,mat,P.MP_BASE_COLOR)
    output(surface_roughness,mat,P.MP_ROUGHNESS)
    world_normal = outward
    if normal:
        texture = ue.load_asset(normal)
        assert texture,normal
        detail = node(mat,ue.MaterialExpressionTextureSample,texture=texture,
                      sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        connect(uv,detail)
        world_normal = expression(mat,{"Face":outward,"Across":across,"Detail":detail}, """
            float2 bump = Detail.xy * .6;
            return normalize(Face * sqrt(saturate(1 - dot(bump,bump)))
                             + Across * bump.x + cross(Across,Face) * bump.y);
            """,ue.CustomMaterialOutputType.CMOT_FLOAT3)
    output(world_normal,mat,P.MP_NORMAL)
    assert not LIB.recompile_material(mat),material
    save(mat)
    return mat


def street_bricks():
    registry = ue.AssetRegistryHelpers.get_asset_registry()
    bricks = registry.get_assets_by_path("/Game/ImportedAssets/TinyTextures/Size512",recursive=True)
    tiny = {}
    for number in (2,3):
        path, = (str(asset.package_name) for asset in bricks
                 if str(asset.asset_class_path.asset_name)=="Texture2D" and f"Bricks_{number:02d}_" in str(asset.asset_name))
        tiny[number] = path
    for key,number,tint in (("AgedRedBrick",2,(1.10,.76,.64)),
                            ("SootBrownBrick",3,(.74,.67,.62)),
                            ("PaleLimeBrick",3,(1.36,1.25,1.03))):
        masonry(ART+"/M_Wall_"+key,tiny[number],None,12,tint,.87)
        textures = REFINEMENT+"/Textures/T_"+key
        masonry(REFINEMENT+"/Materials/M_"+key,textures+"_Color",textures+"_Normal",16,(1,1,1),.86)
    masonry(ART+"/M_FactoryBrick",tiny[2],None,12,(.86,.65,.52),.87)
    for name in ("brick","ochre_brick"):
        textures = STREET+"/Textures/T_"+name
        masonry(STREET+"/Materials/M_"+name,textures+"_Color",textures+"_Normal",16,(1,1,1),.86)
    for key,source,tint,roughness in (("brick","brick",(1.10,.91,.79),.83),
                                      ("ochre","ochre_brick",(1.04,1.02,.92),.85),
                                      ("soot","brick",(.55,.52,.50),.90)):
        textures = STREET+"/Textures/T_"+source
        masonry(STREET+"/RefinedFactory/Materials/M_Factory_"+key,
                textures+"_Color",textures+"_Normal",16,tint,roughness)
