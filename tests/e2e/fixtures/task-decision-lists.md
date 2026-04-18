# Task and Decision Lists

Confluence has two list-shaped macros that aren't normal bullet/ordered
lists: **task lists** (with state TODO/DONE) and **decision lists**.

## Task list

<!--adf:taskList-->

<!--adf:taskItem state="TODO"-->
Draft the design document
<!--/adf:taskItem-->

<!--adf:taskItem state="TODO"-->
Review the PR
<!--/adf:taskItem-->

<!--adf:taskItem state="DONE"-->
Set up CI
<!--/adf:taskItem-->

<!--adf:taskItem state="DONE"-->
Cut the v0.1 release
<!--/adf:taskItem-->

<!--/adf:taskList-->

## Decision list

<!--adf:decisionList-->

<!--adf:decisionItem state="DECIDED"-->
Use Pandoc as the internal AST.
<!--/adf:decisionItem-->

<!--adf:decisionItem state="DECIDED"-->
Express ADF macros via HTML-comment envelope markers in Markdown.
<!--/adf:decisionItem-->

<!--adf:decisionItem state="DECIDED"-->
Publish to PyPI under the name `adflux`.
<!--/adf:decisionItem-->

<!--/adf:decisionList-->

## Mixed paragraph after the lists

These two macros are easy to miss when scanning Confluence --- but they
carry meaningful state for project tracking.
