const CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789';

export function generateRandomSuffix(length = 6) {
  const limit = CHARS.length;
  const maxUnbiased = limit * Math.floor(0x100000000 / limit);
  const buffer = new Uint32Array(length);
  let result = '';
  let filled = 0;

  while (filled < length) {
    crypto.getRandomValues(buffer);

    for (let index = 0; index < buffer.length && filled < length; index += 1) {
      const nextValue = buffer[index];

      if (nextValue === undefined || nextValue >= maxUnbiased) {
        continue;
      }

      result += CHARS[nextValue % limit] ?? '';
      filled += 1;
    }
  }

  return result;
}

export function generateReadableIdBase(name: string) {
  if (!name.trim()) {
    return '';
  }

  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

export function generateReadableId(name: string, suffix = generateRandomSuffix()) {
  const base = generateReadableIdBase(name);

  return base ? `${base}-${suffix}` : '';
}
