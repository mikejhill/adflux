# Page Layouts

Confluence supports multi-column layouts on a page via the
`layoutSection` / `layoutColumn` macros. adflux round-trips these
losslessly using nested HTML-comment envelope markers.

## Two-column layout

<!--adf:layoutSection-->

<!--adf:layoutColumn width="50"-->

### Left column

The left half of the page. Useful for putting related content side by
side, like an explanation paired with an example.

- bullet alpha
- bullet beta

<!--/adf:layoutColumn-->

<!--adf:layoutColumn width="50"-->

### Right column

The right half of the page. Each column can contain any block content,
including its own headings, lists, and code samples.

```python
print("hello from the right column")
```

<!--/adf:layoutColumn-->

<!--/adf:layoutSection-->

## Three-column layout

<!--adf:layoutSection-->

<!--adf:layoutColumn width="33.33"-->

**Plan** --- collect requirements and produce a design.

<!--/adf:layoutColumn-->

<!--adf:layoutColumn width="33.33"-->

**Build** --- implement, test, and review.

<!--/adf:layoutColumn-->

<!--adf:layoutColumn width="33.33"-->

**Ship** --- release, monitor, iterate.

<!--/adf:layoutColumn-->

<!--/adf:layoutSection-->

## After the layout

Layout sections appear in the body sequence just like any other block.
This trailing paragraph follows the three-column layout above.
