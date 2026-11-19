"""Build the moving sky shader and configure distance haze on outdoor views."""
import unreal as ue

from BrightonUpgrade import ACTORS, LIB, P, V, node, connect, output, save, wet_value, factory_asset
from CityLifeCharacters import ROOT
from StreetMaterials import custom_input


CLOUDS = r"""
struct CloudField
{
    float hash(float2 p)
    {
        float3 q = frac(float3(p.x, p.y, p.x) * 0.1031);
        q += dot(q, q.yzx + 33.33);
        return frac((q.x + q.y) * q.z);
    }
    float noise(float2 p)
    {
        float2 i = floor(p);
        float2 f = frac(p);
        f = f*f*(3.0 - 2.0*f);
        return lerp(lerp(hash(i), hash(i + float2(1,0)), f.x),
                    lerp(hash(i + float2(0,1)), hash(i + 1.0), f.x), f.y);
    }
    float density(float2 xy, float layer, float cover)
    {
        float2 p = xy + layer * float2(0.31, 0.48);
        float roll = noise(p) * .57 + noise(p * 2.65 + 8.1) * .26
                   + noise(p * 6.71 + 20.5) * .12 + noise(p*15.8 + 3.4) * .05;
        float heightShape = smoothstep(0.0, .30, layer) * (1.0 - smoothstep(.65, 1.0, layer));
        return saturate((roll - cover + .13 * heightShape) * 4.5) * heightShape;
    }
};
CloudField field;
float3 ray = normalize(-View);
float3 sun = normalize(SunDirection);
float h = saturate(ray.z);
float sunDot = saturate(dot(ray,sun));
float weather = saturate(Wetness);
float daylight = saturate(ZenithTint.g * 2.7 + SunGlow * .52);
float3 horizon = lerp(HorizonTint, HorizonTint * float3(.52,.65,.79), weather * .8);
float3 zenith = lerp(ZenithTint, ZenithTint * float3(.58,.69,.75), weather * .6);
float3 mist = float3(.109,.133,.165);
float3 sky = lerp(mist,lerp(horizon,zenith,pow(h,.54)),smoothstep(0,.12,h));
sky += (1.95 * pow(sunDot, 1800.0) + .18 * pow(sunDot, 11.0)) * SolarTint * SunGlow
       * smoothstep(.006,.085,h);
float horizonFade = smoothstep(.018,.15,h);
if (horizonFade < .001) return sky;

float2 wind = Seconds * float2(.0054,.0021);
float2 cirrusUV = ray.xy * (4.0 / (h + .26)) + Seconds * float2(.0022,-.0007);
float thin = field.noise(float2(cirrusUV.x*1.3,cirrusUV.y*4.0)) * .63
           + field.noise(cirrusUV*3.29+9.0) * .37;
sky += smoothstep(.56,.85,thin) * horizonFade * lerp(.022,.10,daylight)
       * (1.0 - .60 * weather) * lerp(float3(.65,.78,1),float3(1,.81,.67),pow(sunDot,4.0));

// Integrate through one finite cloud layer. Each sample sees a different depth and
// receives less light when another part of the cloud is between it and the sun.
float transmittance = 1;
float3 scatter = 0;
float cover = lerp(.53,.38,weather);
float entry = 1.52 / (h + .20);
float segment = .58 / (h + .27);
float2 sunOffset = sun.xy * .29;
float3 shadow = lerp(float3(.036,.047,.070), float3(.25,.32,.42), daylight);
float3 bright = lerp(float3(.135,.159,.208), float3(.94,.92,.84), daylight);
bright = lerp(bright, bright * lerp(float3(.75,.80,.94), SolarTint + .32, .56),
              SunGlow * (1.0 - daylight * .6));
shadow *= lerp(1.,.76,weather);
bright *= lerp(1.,.61,weather);
[unroll]
for (int i = 0; i < 7; ++i)
{
    float layer = (i + .5) / 7.0;
    float2 xy = ray.xy * (entry + segment*layer) + wind;
    float d = field.density(xy,layer,cover);
    float above = field.density(xy + sunOffset, min(.97,layer + .17),cover);
    float light = saturate(.95 - above*.86 - d*.24);
    float opacity = 1.0 - exp(-d * .77 / (h + .31));
    scatter += transmittance * opacity * lerp(shadow,bright,light);
    transmittance *= 1.0 - opacity;
}
float3 clouds = sky * transmittance + scatter;
return lerp(sky,clouds,horizonFade);
"""


def bake_sky():
    sky = ue.load_asset("/Game/Prologue/Street/Materials/M_Sky")
    assert sky
    LIB.delete_all_material_expressions(sky)
    sky.set_editor_properties(dict(shading_model=ue.MaterialShadingModel.MSM_UNLIT,
                                   is_sky=True, two_sided=True))
    inputs = ("View","HorizonTint","ZenithTint","SolarTint","SunDirection","SunGlow","Seconds","Wetness")
    shader = node(sky,ue.MaterialExpressionCustom,inputs=[custom_input(key) for key in inputs],
        output_type=ue.CustomMaterialOutputType.CMOT_FLOAT3,description="Wind and cloud scattering",code=CLOUDS)
    connect(node(sky,ue.MaterialExpressionCameraVectorWS),shader,"View")
    for name,default in (
        ("HorizonTint",(.57,.29,.19)),("ZenithTint",(.066,.16,.38)),
        ("SolarTint",(1,.60,.39)),("SunDirection",(-.86,.42,.22)),
    ):
        value=node(sky,ue.MaterialExpressionVectorParameter,parameter_name=ue.Name(name),
                   default_value=ue.LinearColor(*default,1))
        connect(value,shader,name,"RGB")
    glow=node(sky,ue.MaterialExpressionScalarParameter,parameter_name=ue.Name("SunGlow"),default_value=.65)
    connect(glow,shader,"SunGlow")
    connect(node(sky,ue.MaterialExpressionTime,ignore_pause=False),shader,"Seconds")
    collection=ue.load_asset("/Game/Prologue/Brighton/Materials/MPC_Weather")
    connect(wet_value(sky,collection),shader,"Wetness")
    output(shader,sky,P.MP_EMISSIVE_COLOR)
    LIB.recompile_material(sky)
    save(sky)
    return sky


def configure_haze(interior=False):
    fog = next((a for a in ACTORS.get_all_level_actors() if isinstance(a,ue.ExponentialHeightFog)),None)
    if not fog:
        return
    fog.set_actor_location(V(0,0,-520 if interior else -65),False,True)
    component = fog.get_component_by_class(ue.ExponentialHeightFogComponent)
    component.set_editor_properties(dict(fog_density=.073,fog_height_falloff=.064,
        start_distance=3500 if interior else 4100,fog_max_opacity=.985,fog_cutoff_distance=68000))
    component.set_volumetric_fog(False)
    component.set_fog_inscattering_color(ue.LinearColor(.109,.133,.165,1))


def night_sky(sky):
    variant=factory_asset(ROOT+"/Materials","MI_NightUnderClouds",ue.MaterialInstanceConstant,
                          ue.MaterialInstanceConstantFactoryNew())
    LIB.set_material_instance_parent(variant,sky)
    for name,tint in (("HorizonTint",(.038,.059,.092)),("ZenithTint",(.007,.018,.040)),
                      ("SolarTint",(.48,.59,.81)),("SunDirection",(.69,-.38,.61))):
        LIB.set_material_instance_vector_parameter_value(variant,ue.Name(name),ue.LinearColor(*tint,1))
    LIB.set_material_instance_scalar_parameter_value(variant,ue.Name("SunGlow"),.032)
    save(variant)
    return variant


def add_night_sky(material):
    actor=next((a for a in ACTORS.get_all_level_actors() if a.actor_has_tag("CityLifeNightSky")),None)
    if actor is None:
        actor=ACTORS.spawn_actor_from_class(ue.StaticMeshActor,V(0,0,0),ue.Rotator())
        actor.set_actor_label("Shared atmospheric sky")
        actor.set_folder_path(ue.Name("Brighton/Atmosphere"))
        actor.tags=[ue.Name("CityLifeNightSky")]
    component=actor.get_component_by_class(ue.StaticMeshComponent)
    component.set_static_mesh(ue.load_asset("/Engine/BasicShapes/Sphere"))
    component.set_material(0,material)
    component.set_collision_profile_name(ue.Name("NoCollision"))
    component.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False))
    actor.set_actor_scale3d(V(1570,1570,1570))
