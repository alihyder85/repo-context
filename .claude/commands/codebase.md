---
description: Query the indexed codebase and answer questions using only retrieved context
---

You are answering a question about the codebase using the code-indexer retrieval tool.

User query: $ARGUMENTS

Follow these steps exactly:

1. Run the retrieval CLI to get relevant context:
   ```
   code-indexer query "$ARGUMENTS" --budget 6000
   ```

2. For each file path and line range returned, read the actual source lines:
   ```
   Read file at the path shown, lines line_start to line_end
   ```

3. Answer the user's question using ONLY the retrieved code. Do not guess or invent code that wasn't in the context.

4. For every claim you make, cite the source as `file_path:line_number`.

5. If the retrieval returns no results, say so clearly and suggest the user run `code-indexer index <repo_path>` first.

Keep your answer concise. Show relevant code snippets inline. Do not summarise files that weren't retrieved.
