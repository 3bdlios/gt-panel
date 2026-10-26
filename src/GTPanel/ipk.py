"""Read IPK data safely without running package scripts."""
import io
import tarfile

class IPKError(Exception):
    pass

def read_ar(data):
    if not data.startswith(b'!<arch>\n'):
        raise IPKError("Invalid IPK archive")

    offset = 8
    members = {}

    while offset < len(data):
        if offset + 60 > len(data):
            raise IPKError("Truncated AR header")

        h = data[offset:offset + 60]
        if h[58:60] != b'`\n':
            raise IPKError("Invalid AR member")

        name = h[:16].decode('ascii').strip().rstrip('/')
        try:
            size = int(h[48:58].strip())
        except ValueError:
            raise IPKError("Invalid member size")

        offset += 60
        if size < 0 or offset + size > len(data):
            raise IPKError("Invalid AR bounds")
        if name in members:
            raise IPKError("Duplicate AR member")

        members[name] = data[offset:offset + size]
        offset += size + (size % 2)

    if offset != len(data):
        raise IPKError("Invalid AR padding")

    return members

def payload(data, allowed):
    members = read_ar(data)

    required = {
        'debian-binary',
        'control.tar.gz',
        'data.tar.gz'
    }

    if set(members) != required:
        raise IPKError("Unexpected IPK members")

    if members['debian-binary'] != b'2.0\n':
        raise IPKError("Unsupported package format")

    # Reject package-maintainer scripts.
    with tarfile.open(
        fileobj=io.BytesIO(members['control.tar.gz']),
        mode='r:gz'
    ) as tf:
        entries = tf.getmembers()
        if len(entries) != 1:
            raise IPKError("Unexpected control entries")
        entry = entries[0]
        if not entry.isfile() or entry.name not in ('control', './control'):
            raise IPKError("Unsupported control archive")
        if entry.size > 65536:
            raise IPKError("Control file too large")
        control_data = tf.extractfile(entry).read(65537)
        if len(control_data) != entry.size:
            raise IPKError("Invalid control file size")

    result = {}
    total = 0

    with tarfile.open(
        fileobj=io.BytesIO(members['data.tar.gz']),
        mode='r:gz'
    ) as tf:
        for m in tf:
            if not m.isfile() or m.mode & 0o7000:
                raise IPKError("Unsafe file type or mode")

            raw = m.name
            if raw.startswith('./'):
                raw = raw[2:]

            path = '/' + raw

            if (
                not raw
                or raw.startswith('/')
                or any(x in ('', '.', '..') for x in raw.split('/'))
                or path not in allowed
                or path in result
            ):
                raise IPKError("Unexpected package path")

            if m.size < 0 or m.size > 32 * 1024 * 1024:
                raise IPKError("Invalid file size")
            total += m.size
            if total > 32 * 1024 * 1024:
                raise IPKError("Package too large")

            content = tf.extractfile(m).read(m.size + 1)
            if len(content) != m.size:
                raise IPKError("Invalid extracted file size")
            result[path] = content

    if set(result) != set(allowed):
        raise IPKError("Package inventory mismatch")

    return result
