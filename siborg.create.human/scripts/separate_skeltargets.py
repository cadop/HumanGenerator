# Build the recalculated blendshapes from targets to exclude transformations due to skeletal deformation
# Write skeletal transformations to a separate .skeltargets file

import os
from pxr import Usd, UsdSkel, UsdGeom, Gf, Sdf, Vt
import numpy as np
import json


def blendshape_to_skeltarget(prim: Usd.Prim, blendshape_name: str, output_path: str):
    """Creates a .skeltarget file for a given blendshape. The file contains the transformations applied to the skeleton
    joints when referencing the joint helper geometry after the blendshape has been applied."""

    # Apply the blendshape to the mesh at 100% weight
    points = compute_blendshape_points(prim, blendshape_name, 1)

    # Move the skeleton to the points defined by the helper geometry
    skel_path = UsdSkel.BindingAPI(prim).GetSkeletonRel().GetTargets()[0]
    skel = UsdSkel.Skeleton.Get(prim.GetStage(), skel_path)
    xforms = joints_from_points(skel, points, 0)

    # Save the skeletal transformations to a .skeltarget file. A .skeltarget file is named after the blendshape it
    # corresponds to and takes the form of a JSON file with the following structure:
    # {
    #   "blendshape": "blendshape_name",
    #    "skeleton": {
    #         "joint_path": {
    #             "translation": [x, y, z],
    #             "rotation": {
    #                 "axis": [x, y, z],
    #                 "angle": angle
    #             },
    #             "scale": [x, y, z]
    #         }
    #     }
    # }
    joints = skel.GetJointsAttr().Get()
    data = {"blendshape": blendshape_name, "skeleton": {}}
    for joint, xform in zip(joints, xforms):
        xform.Orthonormalize()
        translation = list(xform.ExtractTranslation())

        rotation = xform.ExtractRotation()
        rotation = {"axis": list(rotation.GetAxis()), "angle": rotation.GetAngle()}

        scale = list(Gf.Vec3d(*(v.GetLength() for v in xform.ExtractRotationMatrix())))
        data["skeleton"][joint] = {"translation": translation, "rotation": rotation, "scale": scale}

    with open(output_path, "w") as f:
        json.dump(data, f, indent=4)

    # Skeltargets are effectively just skeletal animations, so we can also save the skeletal transformations to a .usda
    # stage = Usd.Stage.CreateInMemory()
    # skelroot = UsdSkel.Root.Define(stage, prim.GetPath().AppendChild("skeltargets"))
    # stage.SetDefaultPrim(skelroot.GetPrim())
    # skel = UsdSkel.Skeleton.Define(stage, skelroot.GetPath().AppendChild(f"skeleton_{blendshape_name}"))
    # skelCache = UsdSkel.Cache()
    # skelQuery = skelCache.GetSkelQuery(skel)
    # skel.CreateJointsAttr(skelQuery.GetJointOrder())
    # stage.GetRootLayer().Export(f"{output_path}.usda")


def calculate_skeltarget_verts(prim: Usd.Prim, skeltarget_path: str) -> Vt.Vec3fArray:
    """Applies the skeletal transformations defined in a .skeltarget file to the skeleton joints. There should be a mesh
    in the scene that is already bound and skinned to the skeleton.

    Parameters:
    ------------
    prim: Usd.Prim
        The skelroot containing the skeleton and mesh
    skeltarget_path: str
        The path to the .skeltarget file containing the skeletal transformations

    Returns:
    ------------
    Vt.Vec3fArray
        The new vertices of the mesh after the skeletal transformations have been applied

    """
    # Load the .skeltarget file
    with open(skeltarget_path, "r") as f:
        skeltarget = json.load(f)

    # Read the skeletal transformations from the .skeltarget file
    num_joints = len(skeltarget["skeleton"])
    translations = Vt.Vec3fArray(num_joints)
    rotations = Vt.QuatfArray(num_joints)
    scales = Vt.Vec3hArray(num_joints)

    for i, (joint, data) in enumerate(skeltarget["skeleton"].items()):
        translations[i] = Gf.Vec3f(*data["translation"])

        rotation = data["rotation"]
        quatd = Gf.Rotation(rotation["axis"], rotation["angle"]).GetQuat()
        rotations[i] = Gf.Quatf(quatd)

        scales[i] = Gf.Vec3h(*data["scale"])

    xforms = UsdSkel.MakeTransforms(translations, rotations, scales)

    # Get the skeleton through the binding API. We assume the first target is the skeleton we want to use
    skel_path = UsdSkel.BindingAPI(prim).GetSkeletonRel().GetTargets()[0]
    skel = UsdSkel.Skeleton.Get(prim.GetStage(), skel_path)
    body = prim.GetChild("body")

    # Get the animation of the skeleton
    anim_path = UsdSkel.BindingAPI(skel).GetAnimationSourceRel().GetTargets()[0]
    anim = UsdSkel.Animation.Get(prim.GetStage(), anim_path)
    # Posing is temporary: author it in the session layer so it never reaches an exported layer
    stage = prim.GetStage()
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        anim.SetTransforms(xforms, 0)

    # Query the skeleton and geometry
    skelRoot = UsdSkel.Root(prim)
    skelCache = UsdSkel.Cache()
    skelCache.Populate(skelRoot, Usd.PrimDefaultPredicate)
    skelQuery = skelCache.GetSkelQuery(skel)
    skinningQuery = skelCache.GetSkinningQuery(body)

    # Get the points of the mesh
    points = body.GetAttribute("points").Get(0)

    # Apply the joint animation to the skinned mesh
    skinned_points = applyJointAnimation(skinningQuery, skelQuery, 0, points)

    # # Reset the joint positions to rest pose so they don't stack
    xforms = skelQuery.ComputeJointLocalTransforms(0, True)
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        anim.SetTransforms(xforms, 0)

    return skinned_points


def applyJointAnimation(
    skinning_query: UsdSkel.SkinningQuery, skel_query: UsdSkel.SkeletonQuery, time: float, points: Vt.Vec3fArray
):
    """Apply the joint animation to the skinned mesh at a given time. Adapted from
    https://github.com/TheFoundryVisionmongers/KatanaUsdPlugins/blob/main/lib/usdKatana/utils.cpp"""

    # Get the skinning transform from the skeleton.
    skinning_xforms = skel_query.ComputeSkinningTransforms(time)

    # Get the prim's points first and then skin them.
    skinned_points = Vt.Vec3fArray.FromNumpy(np.array(points, copy=True))
    skinning_query.ComputeSkinnedPoints(skinning_xforms, skinned_points, time)

    # Apply transforms to get the points in mesh prim space instead of skeleton space.
    xform_cache = UsdGeom.XformCache(time)
    skel_prim = skel_query.GetPrim()

    skel_local_to_world = xform_cache.GetLocalToWorldTransform(skel_prim)
    prim_world_to_local = xform_cache.GetLocalToWorldTransform(skinning_query.GetPrim()).GetInverse()
    skel_to_prim_local = np.array(skel_local_to_world * prim_world_to_local)

    # Transform all points at once (USD matrices are row-major, so points are row vectors on the left). Assigning
    # Gf.Vec3f per element from Python fails on newer pxr builds and was slow anyway.
    pts = np.array(skinned_points, dtype=np.float64)
    pts = np.c_[pts, np.ones(len(pts))] @ skel_to_prim_local
    return Vt.Vec3fArray.FromNumpy(pts[:, :3].astype(np.float32))


def separate_blendshape(prim: Usd.Prim, blendshape: UsdSkel.BlendShape, skeltarget_path: str) -> UsdSkel.BlendShape:
    """Subtracts the mesh deformation due to skeletal transformations from deformation caused by the blendshape  to
    create a new blendshape without the corresponding skeletal transformation deformation. The resulting blendshape is
    added to the prim."""
    # Get the mesh
    body = prim.GetChild("body")
    # Get the mesh points before any transformation is applied
    default_points = np.array(body.GetAttribute("points").Get())

    # Calculate the new vertices of the blendshape after the skeletal transformations have been applied
    skel_deformation = np.array(calculate_skeltarget_verts(prim, skeltarget_path))

    # Calculate the offset between the original mesh and the mesh after skeletal deformation
    skeletal_deformation_offset = skel_deformation - default_points

    # Get the blendshape offsets
    blendshape_offsets = np.array(blendshape.GetOffsetsAttr().Get())
    blendshape_indices = np.array(blendshape.GetPointIndicesAttr().Get())

    # Subtract the skeletal deformation from the blendshape offsets. Moving joints also drags vertices the original
    # target never touched (e.g. lengthening the thigh moves the shin), so the corrected blendshape must cover every
    # vertex the skeleton moves, not just the original point indices.
    dense_offsets = np.zeros_like(default_points)
    dense_offsets[blendshape_indices] = blendshape_offsets
    dense_offsets -= skeletal_deformation_offset
    affected = np.any(np.abs(skeletal_deformation_offset) > 1e-7, axis=1)
    affected[blendshape_indices] = True
    blendshape_indices = np.where(affected)[0].astype(np.int32)
    corrected_offsets = dense_offsets[blendshape_indices].astype(np.float32)

    # Overwrite the blendshape with the corrected offsets
    blendshape.GetOffsetsAttr().Set(Vt.Vec3fArray().FromNumpy(corrected_offsets))
    blendshape.GetPointIndicesAttr().Set(Vt.IntArray().FromNumpy(blendshape_indices))

    # Mark the blendshape as separated so it is never separated a second time
    blendshape.GetPrim().SetCustomDataByKey("skelfree", True)
    blendshape.GetPrim().SetCustomDataByKey("skeltarget", os.path.basename(skeltarget_path))
    return blendshape


def separate_all(src_path: str, out_path: str, skeltargets_dir: str) -> str:
    """Separate skeletal deformation from every blendshape bound to the body in `src_path`.

    `src_path` is never modified. The corrected blendshapes are written as overrides to a new layer at `out_path`
    which sublayers `src_path`, and one .skeltarget file per blendshape is written to `skeltargets_dir`. The output
    layer is rebuilt from scratch on every run, so running this repeatedly gives the same result.

    Returns the path of the output layer.
    """
    src_path = os.path.abspath(src_path)
    out_path = os.path.abspath(out_path)
    if os.path.normcase(src_path) == os.path.normcase(out_path):
        raise ValueError("The output layer must not overwrite the source layer")

    # Compose a fresh, empty override layer over the untouched source. All edits land in the override layer.
    layer = Sdf.Layer.CreateAnonymous(".usda")
    layer.subLayerPaths.append(src_path)
    # Stage metadata is only read from the root layer, so carry it over from the source
    src_layer = Sdf.Layer.FindOrOpen(src_path)
    authored = set(src_layer.pseudoRoot.ListInfoKeys())
    for key in ("defaultPrim", "startTimeCode", "endTimeCode", "timeCodesPerSecond", "framesPerSecond"):
        if key in authored:
            setattr(layer, key, getattr(src_layer, key))
    stage = Usd.Stage.Open(layer)
    if "upAxis" in authored:
        UsdGeom.SetStageUpAxis(stage, src_layer.pseudoRoot.GetInfo("upAxis"))
    if "metersPerUnit" in authored:
        UsdGeom.SetStageMetersPerUnit(stage, src_layer.pseudoRoot.GetInfo("metersPerUnit"))
    prim = stage.GetDefaultPrim().GetChild("skel_root")
    mesh = prim.GetChild("body")
    targets = UsdSkel.BindingAPI(mesh).GetBlendShapeTargetsRel().GetTargets()

    # Refuse input that has already been separated, otherwise the skeletal deformation is subtracted twice
    already = [p.name for p in targets if stage.GetPrimAtPath(p).GetCustomDataByKey("skelfree")]
    if already:
        raise ValueError(
            f"{src_path} contains blendshapes that were already separated (e.g. {already[0]}). "
            "Pass the original human_base.usd produced by buildusd.py."
        )

    os.makedirs(skeltargets_dir, exist_ok=True)
    for blendshape_path in targets:
        blendshape = UsdSkel.BlendShape.Get(stage, blendshape_path)
        blendshape_name = blendshape.GetPrim().GetName()
        # Store the skeletal transformations in a .skeltarget file
        skeltarget_path = os.path.join(skeltargets_dir, f"{blendshape_name}.skeltarget")
        blendshape_to_skeltarget(prim, blendshape_name, skeltarget_path)
        # Override the blendshape with a version that excludes the skeletal deformation
        separate_blendshape(prim, blendshape, skeltarget_path)
        print(f"Removed skeletal deformation from {blendshape_name:>31}")

    # Reference the source relative to the output so the pair can be moved together. Edit a detached copy so the open
    # stage doesn't try to recompose with a relative path it can't resolve from an anonymous layer.
    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)
    out_layer = Sdf.Layer.CreateAnonymous(".usda")
    out_layer.TransferContent(layer)
    out_layer.subLayerPaths[0] = os.path.relpath(src_path, out_dir).replace(os.sep, "/")
    out_layer.Export(out_path)
    return out_path


def skel_from_skeltarget(prim: Usd.Prim, skeltarget_path: str):
    """Create a new skeleton from a .skeltarget file"""
    with open(skeltarget_path, "r") as f:
        skeltarget = json.load(f)

    skelroot = UsdSkel.Root.Define(prim.GetStage(), prim.GetPath().AppendChild("skeltargets"))
    skel = UsdSkel.Skeleton.Define(
        prim.GetStage(), skelroot.GetPath().AppendChild(f"skeleton_{skeltarget['blendshape']}")
    )
    skel.CreateJointsAttr(Vt.TokenArray(skeltarget["skeleton"].keys()))

    # Apply the skeletal transformations to the skeleton joints
    num_joints = len(skel.GetJointsAttr().Get())
    translations = Vt.Vec3fArray(num_joints)
    rotations = Vt.QuatfArray(num_joints)
    scales = Vt.Vec3hArray(num_joints)

    for i, (joint, data) in enumerate(skeltarget["skeleton"].items()):
        translations[i] = Gf.Vec3f(*data["translation"])

        rotation = data["rotation"]
        quatd = Gf.Rotation(rotation["axis"], rotation["angle"]).GetQuat()
        rotations[i] = Gf.Quatf(quatd)

        scales[i] = Gf.Vec3h(*data["scale"])

    xforms = UsdSkel.MakeTransforms(translations, rotations, scales)
    skel.CreateRestTransformsAttr().Set(xforms, Usd.TimeCode.Default())


def compute_blendshape_points(prim: Usd.Prim, blendshape_name: str, weight: float) -> np.array:
    """Compute the new points of a mesh after a blendshape has been applied."""
    body = prim.GetChild("body")
    mesh_binding = UsdSkel.BindingAPI(body)
    blend_query = UsdSkel.BlendShapeQuery(mesh_binding)
    # Use updated blendshape weights to compute subShapeWeights, blendShapeIndices, and subShapeIndices
    # Get just the blendshapes that apply to this mesh
    blendshapes_on_body = body.GetAttribute("skel:blendShapes").Get()
    blendshapes_on_body = np.array(blendshapes_on_body)
    # Zero out the weights for all blendshapes applied to the body
    weights_on_body = np.zeros(len(blendshapes_on_body))
    # Set the weight for the blendshape we're interested in
    index = np.where(blendshapes_on_body == blendshape_name)
    weights_on_body[index] = weight
    # Compute the new points
    subShapeWeights, blendShapeIndices, subShapeIndices = blend_query.ComputeSubShapeWeights(weights_on_body)
    blendShapePointIndices = blend_query.ComputeBlendShapePointIndices()
    subShapePointOffset = blend_query.ComputeSubShapePointOffsets()
    original_points = body.GetAttribute("points").Get()
    points_to_calculate = Vt.Vec3fArray.FromNumpy(np.array(original_points, copy=True))
    success = blend_query.ComputeDeformedPoints(
        subShapeWeights,
        blendShapeIndices,
        subShapeIndices,
        blendShapePointIndices,
        subShapePointOffset,
        points_to_calculate,
    )
    if success:
        # Compare old points to new points
        new_points = np.array(points_to_calculate)
        # See what changed
        changed = np.where(original_points != new_points)[0]
        # print(f"Changed: {changed}")
    else:
        raise ValueError("Failed to compute deformed points")

    return new_points


def joints_from_points(resize_skel: UsdSkel.Skeleton, points: Vt.Vec3fArray, time: int) -> Vt.Matrix4dArray:
    """Compute the joint transforms for a skeleton from a set of points. Requires that the skeleton has customdata
    with a mapping from each bone to its set of vertices. Transforms are returned in local space."""
    # Get mapping from each bone to its set of vertices
    bone_vertices_idxs = resize_skel.GetPrim().GetCustomData()

    # Query the resizing skeleton
    skel_cache = UsdSkel.Cache()
    skel_query = skel_cache.GetSkelQuery(resize_skel)

    # Get the list of bones
    joints = skel_query.GetJointOrder()

    # Get the points attribute as a numpy array for multi-indexing
    points = np.array(points)
    # Get transforms for each bone
    xforms = []
    for joint in joints:
        vert_idxs = np.array(bone_vertices_idxs[joint])
        verts = points[vert_idxs]
        xforms.append(compute_transform(verts))

    # Convert to local space
    xforms = Vt.Matrix4dArray().FromNumpy(np.array(xforms))
    topo = UsdSkel.Topology(joints)
    return UsdSkel.ComputeJointLocalTransforms(topo, xforms, Gf.Matrix4d(np.eye(4)))


def compute_transform(head_vertices: np.array) -> Gf.Matrix4d:
    """Compute the rest and bind transforms for a joint"""
    head_position = np.mean(head_vertices, axis=0)
    # Bind transform is in world space
    transform = np.eye(4)
    transform[:3, 3] = head_position

    return Gf.Matrix4d(transform.T)


if __name__ == "__main__":
    import argparse

    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    parser = argparse.ArgumentParser(description="Separate skeletal deformation from blendshapes. Never modifies --src.")
    parser.add_argument("--src", default=os.path.join(data_path, "human_base.usd"), help="stage built by buildusd.py")
    parser.add_argument("--out", default=os.path.join(data_path, "human_base_separated.usda"),
                        help="override layer to (re)write; sublayers --src")
    parser.add_argument("--skeltargets-dir", default=os.path.join(data_path, "skeltargets"))
    args = parser.parse_args()

    out = separate_all(args.src, args.out, args.skeltargets_dir)
    print(f"Wrote {out}. Skeltargets have been written to {args.skeltargets_dir}")
