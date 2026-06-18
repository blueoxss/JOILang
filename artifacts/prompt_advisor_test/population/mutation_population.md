# Prompt Advisor Mutation Population

## Summary
- candidate genomes: 12
- mutation intent groups: aggressive, conservative, dataflow_repair, minimality_repair, receiver_repair, service_repair, skeleton_repair
- conservative candidate: True
- aggressive candidate: True

## Candidates
### cand_000_canonical_service_name
- intent: service_repair
- source patches: patch_000_canonical_service_name
- active blocks: 01, 02, 03, 06
- families: Canonical_Service_Name
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_001_minimality
- intent: minimality_repair
- source patches: patch_001_minimality
- active blocks: 01, 02, 03, 06
- families: Minimality
- token cost: medium
- regression risk: medium
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_002_output_schema
- intent: minimality_repair
- source patches: patch_002_output_schema
- active blocks: 01, 02, 03, 06
- families: Output_Schema
- token cost: medium
- regression risk: medium
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_003_enum_grounding
- intent: service_repair
- source patches: patch_003_enum_grounding
- active blocks: 01, 02, 03, 06
- families: Enum_Grounding
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_004_dataflow
- intent: dataflow_repair
- source patches: patch_004_dataflow
- active blocks: 01, 02, 03, 06
- families: Dataflow
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_005_skeleton
- intent: skeleton_repair
- source patches: patch_005_skeleton
- active blocks: 01, 02, 03, 06
- families: Skeleton
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_006_det_helper_cluster
- intent: skeleton_repair
- source patches: patch_006_det_helper
- active blocks: 01, 02, 03, 06
- families: DET_Helper
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_007_receiver_tag_preservation_cluster
- intent: receiver_repair
- source patches: patch_007_receiver_tag_preservation
- active blocks: 01, 02, 03, 06
- families: Receiver_Tag_Preservation
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_008_owner_device_rule_cluster
- intent: receiver_repair
- source patches: patch_008_owner_device_rule
- active blocks: 01, 02, 03, 06
- families: Owner_Device_Rule
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_009_service_mapping_cluster
- intent: service_repair
- source patches: patch_009_service_mapping
- active blocks: 01, 02, 03, 06
- families: Service_Mapping
- token cost: medium
- regression risk: low
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_010_low_cost_low_risk
- intent: conservative
- source patches: patch_000_canonical_service_name, patch_001_minimality, patch_002_output_schema
- active blocks: 01, 02, 03, 06
- families: Canonical_Service_Name, Minimality, Output_Schema
- token cost: medium
- regression risk: medium
- validation: Rerun strict DET on evidence rows, then related category rows.

### cand_011_high_priority_bundle
- intent: aggressive
- source patches: patch_000_canonical_service_name, patch_001_minimality, patch_002_output_schema, patch_003_enum_grounding, patch_004_dataflow, patch_005_skeleton
- active blocks: 01, 02, 03, 06
- families: Canonical_Service_Name, Dataflow, Enum_Grounding, Minimality, Output_Schema, Skeleton
- token cost: medium
- regression risk: medium
- validation: Rerun strict DET on evidence rows, then related category rows.
