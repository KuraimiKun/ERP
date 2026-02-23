"""
Deduplicate PO files by removing duplicate msgid entries (keeping the first occurrence).
"""
import re
import sys


def dedup_po(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into entries using double newlines as separators
    # Each entry is a msgid+msgstr pair (possibly with comments)
    entries = re.split(r'\n\n+', content.strip())

    seen_msgids = set()
    kept_entries = []
    removed = 0

    for entry in entries:
        # Find msgid in this entry
        m = re.search(r'^msgid\s+"((?:[^"\\]|\\.)*)"', entry, re.MULTILINE)
        if m:
            msgid_val = m.group(1)
            # For multiline msgid, collect continuation lines
            after_msgid = entry[m.end():]
            for cont in re.finditer(r'^"((?:[^"\\]|\\.)*)"', after_msgid, re.MULTILINE):
                msgid_val += cont.group(1)
                after_pos = cont.end()
                # Stop at msgstr
                if re.match(r'^\s*$', after_msgid[after_pos:after_pos+1]):
                    break

            if msgid_val == '':
                # Header entry - always keep
                kept_entries.append(entry)
            elif msgid_val not in seen_msgids:
                seen_msgids.add(msgid_val)
                kept_entries.append(entry)
            else:
                removed += 1
        else:
            # No msgid (comment-only block, etc.) - keep it
            kept_entries.append(entry)

    new_content = '\n\n'.join(kept_entries) + '\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f'{filepath}: kept {len(seen_msgids)} unique msgids, removed {removed} duplicates')


if __name__ == '__main__':
    paths = sys.argv[1:] if len(sys.argv) > 1 else [
        'locale/ar/LC_MESSAGES/django.po',
        'locale/id/LC_MESSAGES/django.po',
    ]
    for path in paths:
        dedup_po(path)
