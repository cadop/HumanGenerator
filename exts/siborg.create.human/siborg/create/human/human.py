def init_human(self):
    """Initialize the human and set some required files from disk. This
        includes the skeleton and any proxies (hair, clothes, accessories etc.)
        The weights from the base skeleton must be transfered to the chosen
        skeleton or else there will be unweighted verts on the meshes.
        """
    self.human = human.Human(files3d.loadMesh(
        mh.getSysDataPath("3dobjs/base.obj"), maxFaces=5))
    # set the makehuman instance human so that features (eg skeletons) can
    # access it globally
    self.G.app.selectedHuman = self.human
    humanmodifier.loadModifiers(mh.getSysDataPath(
        "modifiers/modeling_modifiers.json"), self.human)
    # Add eyes
    # self.add_proxy(data_path("eyes/high-poly/high-poly.mhpxy"), "eyes")
    self.base_skel = skeleton.load(
        mh.getSysDataPath("rigs/default.mhskel"),
        self.human.meshData,
    )
    # cmu_skel = skeleton.load(data_path("rigs/cmu_mb.mhskel"), self.human.meshData)
    # Build joint weights on our chosen skeleton, derived from the base
    # skeleton
    # cmu_skel.autoBuildWeightReferences(self.base_skel)

    self.human.setBaseSkeleton(self.base_skel)
    # Actually add the skeleton
    # self.human.setSkeleton(self.base_skel)
    self.human.applyAllTargets()
