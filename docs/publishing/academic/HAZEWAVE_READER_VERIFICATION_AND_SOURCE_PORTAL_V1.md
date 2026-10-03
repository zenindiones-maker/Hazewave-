# HAZEWAVE Reader Verification & Source Portal v1

## 1. Goal

A skeptical student, professor or researcher should be able to ask:

> Where did Hazewave get this?

and reach the underlying source trail quickly.

## 2. Book citation layer

Print/ebook includes:
- note marker;
- exact citation;
- page/section/figure;
- DOI or stable identifier where available.

## 3. Public source portal

Canonical pattern:

```text
hazewave.com/books/{BOOK_ID}/sources
hazewave.com/books/{BOOK_ID}/{CHAPTER_ID}/sources
hazewave.com/claims/{CLAIM_ID}
hazewave.com/sources/{SOURCE_ID}
```

## 4. Claim page

Public fields may include:

```text
CLAIM_ID
BOOK / EDITION
PAGE / CHAPTER
CLAIM SUMMARY
EVIDENCE STATUS
SOURCE LIST
EXACT LOCATORS
COUNTEREVIDENCE
EDITORIAL NOTE
LAST REVIEWED
CORRECTION HISTORY
```

Do not publish copyrighted source text beyond lawful quotation.

## 5. Source page

Fields:

- full citation;
- DOI;
- ISBN/ISSN;
- archive;
- object ID;
- catalogue number;
- stable URL;
- language;
- access status;
- why used;
- book locations citing it.

## 6. Museum/object linking

For an object:
- institution;
- collection;
- accession number;
- object name;
- dating;
- provenance note;
- catalogue URL;
- rights.

## 7. Archive linking

For archive materials:
- archive;
- collection;
- box/folder;
- call number;
- item;
- date;
- digital surrogate if permitted.

## 8. Audio source linking

For recordings:
- performer;
- recorder;
- date;
- location;
- collection;
- catalogue/matrix ID;
- carrier;
- archive/label;
- rights;
- exact timestamp used.

## 9. Version-aware citations

Claim pages must know the edition.

Example:

```text
HW-ACAD-001
EDITION 1.0
PAGE 147
CLAIM HW001-C08-031
```

If pagination changes, old references remain resolvable through edition metadata.

## 10. Correction history

Never silently rewrite a materially contested claim.

Public record:

```text
DATE
OLD STATUS
NEW STATUS
CHANGE
REASON
SOURCE / CORRECTION
AFFECTED EDITIONS
```

## 11. Link durability

Prefer:
- DOI;
- Handle;
- ARK;
- library permalink;
- museum object permalink;
- national archive identifier.

Normal URLs are supplemental when no persistent ID exists.

## 12. Paywalled sources

A source can be legitimate even if paywalled.

Provide:
- full citation;
- DOI;
- journal;
- volume/issue;
- pages;
- library-search metadata.

Do not illegally mirror copyrighted publications.

## 13. Reader annotations

Future feature:
- report a broken link;
- report a citation mismatch;
- submit counterevidence;
- suggest newer scholarship.

Submissions enter editorial review; they do not directly change the book.

## 14. Machine-readable export

Future API/download may expose:
- CSL-JSON;
- BibTeX;
- RIS;
- claim/source JSON;
- figure metadata;
- audio metadata.

## 15. QR policy

QR codes point to Hazewave-controlled stable routes.

No QR should depend permanently on a social-media post.

Redirect targets may change; canonical route remains.

## 16. Privacy / reviewer protection

The source portal exposes evidence, not confidential peer-review identities unless reviewers consent.

## 17. Success metric

A student should be able to:

1. find a claim;
2. identify the source;
3. locate the relevant page/object/recording;
4. see whether the claim is disputed;
5. independently inspect the evidence where access permits.
