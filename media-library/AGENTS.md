# Documentation location

- The user keeps persistent Folio documentation in `media-library/documents/`. Create new specifications, investigation reports, planning notes and verification records there.
- Root `README.md` / `README.ja.md` remain repository entry points. Use links to the documents folder; do not duplicate application guides beside the source files.
- Resolve relative document links from the document's actual folder. Instructions for running the application or tests must use `media-library/` as the working directory, not `media-library/documents/`.
- Preserve the read-only status of synced files under the repository's `sources/` directory.

## Publishing documentation

- The user requests that newly created or updated documentation normally be committed and pushed to GitHub as part of the task, unless they explicitly ask to keep it local or unpublished.
- Commit only the task's documentation and related instruction changes; do not include unrelated application changes or credentials. Report the push result and a GitHub link to the main document.
