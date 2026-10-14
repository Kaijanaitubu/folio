# Pawchive media filter

Video-only posts are rejected in individual imports and reported as skipped in batches. Image/video mixed posts require individual confirmation and are skipped in batches. Archives and unrecognized attachments are marked uncertain: individual confirmation, batch skip with reason. No attachments is unknown; retain existing metadata-only behavior with a warning. Classification uses file metadata extensions only and never downloads videos or opens archives. Images alone do not establish that a post is a comic; a video with an image preview is mixed. This cannot reliably distinguish preview images from independent artwork.

Kemono bookmark conversion also uses this filter during subsequent Pawchive import. Existing records are not removed.
