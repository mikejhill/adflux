# Extension Macros

Confluence "macros" (info, table-of-contents, jira-issues, etc.) are
encoded in ADF as `extension` (block) nodes. adflux preserves them via
HTML-comment envelope markers; the optional `parameters` attribute is a
JSON-encoded blob so arbitrary nested data survives the round trip.

## Block extension --- table of contents

<!--adf:extension extensionKey="toc" extensionType="com.atlassian.confluence.macro.core" parameters="e30="-->
<!--/adf:extension-->

## Block extension --- info macro

<!--adf:extension extensionKey="info" extensionType="com.atlassian.confluence.macro.core" parameters="e30="-->
<!--/adf:extension-->

## Block extension --- children-display

<!--adf:extension extensionKey="children" extensionType="com.atlassian.confluence.macro.core" parameters="e30="-->
<!--/adf:extension-->

## After the macros

The three macros above each occupy their own block; adflux emits one
`extension` ADF node per envelope.
