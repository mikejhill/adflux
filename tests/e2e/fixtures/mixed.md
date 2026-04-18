# Mixed ADF Macros

A page combining several ADF-specific macros that Confluence renders
natively: panels, status badges, expand sections, and code blocks with
language hints.

## Status badges

The status macro is inline. Project state: <!--adf:status text="In Progress" color="yellow"/-->
--- and build state: <!--adf:status text="Passing" color="green"/-->.

## Expand section

<details><summary>Implementation notes</summary>

Hidden by default, expandable on click. Useful for collapsing long
auxiliary content.

- supports nested lists
- supports formatted **text**

</details>

## Info panel preceding an expand

> [!NOTE]
>
> Heads up --- read the details below before proceeding.

<details><summary>Details</summary>

The expansion contains the actual instructions.

</details>

## Multi-language code blocks

```javascript
const x = 42;
console.log(x);
```

```sql
SELECT id, title FROM pages WHERE space_id = $1;
```

```yaml
name: adflux
version: 0.1.0
```

## Final paragraph

This concludes the mixed-macros fixture.
