# SkelTargetAPI Design

Apply MakeHuman modifiers to a skinned human without reskinning. One weight per target drives both the mesh and the skeleton, so modifier values can be animated.

## Idea

UsdSkel BlendShapes only offset mesh points; there's no joint blendshape. We store each target's joint translation offsets on the same BlendShape prim. Modifier values are the authored state. Our evaluator turns them into blendshape weights (UsdSkel applies those to the mesh) and uses the same weights to compute joint translations.

## Schemas

| Schema | Applies to | Contents |
|---|---|---|
| `HumanModifierGroup` | typed | UI section; child order = slider order |
| `HumanModifier` | typed | `value` (animatable), `defaultValue`, `knots[]`, `labels[]`, `label`, `image`, `normalizationGroup` |
| `ModifierTargetAPI` | BlendShape | `rel drivers` + `labels[]` |
| `SkelTargetAPI` | BlendShape | `joints[]` + `translationOffsets[]` |

Each modifier maps a slider value onto labels by piecewise-linear interpolation over knots. A blendshape's weight is the product of its drivers' label weights:

```
weight(shape) = Π labelWeight(driver_i, label_i)
```

Macro targets (e.g. `female-young-averagemuscle-averageweight-maxheight`) have several drivers. All 348 macro targets decompose this way, and knots match `macro.json` within 0.02.

```
class "SkelTargetAPI" (inherits = </APISchemaBase>)   # apiSchemaCanOnlyApplyTo = ["BlendShape"]
{
    uniform token[]    skelTarget:joints = []               # joint paths
    uniform vector3f[] skelTarget:translationOffsets = []   # local delta per joint at weight 1
}
```

Source of truth: `siborg.create.human/schema/schema.usda`.

## Evaluation

```
jointTranslations(t) = restTranslations + Σ_b weight_b(t) · translationOffsets_b
```

Bind transforms, skin weights, rotations and scales are unchanged. This is exact because joints only translate and LBS is linear in translations. `validate_skeltargets.py` results:

| Case | Max error |
|---|---|
| 140 armslegs targets, weight 1 | 1.7e-6 |
| One target at weight 0.5 | 9.8e-7 |
| 3 arm targets combined | 3.0e-6 |
| Posed vs full reskin | 0.011 (mesh 16.7 tall) |
| Naive (original shapes + moved joints) | 0.36 |

Typed attributes over customData: real typed arrays, live on the same prim as the weight, compose per attribute, and still read fine where the schema isn't registered.

## User animation

- UsdSkel ignores joints whose animation lacks translations, so real animations author translations and would override modeled bone lengths.
- A skeleton has one animation source. A conform step writes a `modeling.usda` layer over the bound SkelAnimation (modeled translations, blendshape weights), passing user rotations/scales through and copying root translation.
- For exporters that ignore rest transforms: bake bind transforms and rest points once (no reskin).

## Registration

Codeless schema (`skipCodeGeneration = true`). It must be registered before USD initializes; registering later is ignored. In Kit that means app launch (`PXR_PLUGINPATH_NAME`), not the extension. Until then, code reads attributes by name.

## Limits

- Joints must stay translation-only. Some targets turn bones up to ~6°; fine now, but would need rotation offsets if joints get oriented along bones.
- No inbetweens (MakeHuman doesn't use them).
- Macro skeletal offsets untested (144 height targets have only 20 distinct contents).

## Status

- **Done:** buildusd authors modifier prims and `ModifierTargetAPI`; `separate_all` authors `SkelTargetAPI`. All 480 shapes reconstruct exactly.
- **Next:** generate `generatedSchema.usda` + `plugInfo.json`, register in the Kit app.
- **Then:** runtime evaluator, UI from prim queries, conform step.
