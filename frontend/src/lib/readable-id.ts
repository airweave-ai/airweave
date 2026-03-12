/**
 * Shared readable ID generation using CSPRNG (crypto.getRandomValues).
 */

const CHARS = "abcdefghijklmnopqrstuvwxyz0123456789";

/**
 * Generate a cryptographically random alphanumeric suffix.
 *
 * @param length - Length of the suffix (default 6)
 * @returns Random lowercase alphanumeric string
 */
export function generateRandomSuffix(length = 6): string {
  const limit = CHARS.length;
  // Largest multiple of `limit` that fits in a Uint32.  Values at or
  // above this threshold would produce modulo bias and are discarded.
  const maxUnbiased = limit * Math.floor(0x100000000 / limit);
  const buf = new Uint32Array(length);
  let result = "";
  let filled = 0;
  while (filled < length) {
    crypto.getRandomValues(buf);
    for (let j = 0; j < buf.length && filled < length; j++) {
      if (buf[j] < maxUnbiased) {
        result += CHARS[buf[j] % limit];
        filled++;
      }
    }
  }
  return result;
}

/**
 * Sanitize a name into a readable ID base (without suffix).
 *
 * Transforms to lowercase, replaces spaces with hyphens, strips
 * special characters.
 *
 * @param name - Human-readable name to transform
 * @returns Sanitized slug, or empty string if name is blank
 */
export function generateReadableIdBase(name: string): string {
  if (!name || name.trim() === "") return "";

  let readable_id = name.toLowerCase().trim();

  // Remove characters that aren't letters, numbers, or spaces
  readable_id = readable_id.replace(/[^a-z0-9\s]/g, "");

  // Replace spaces with hyphens
  readable_id = readable_id.replace(/\s+/g, "-");

  // Collapse consecutive hyphens
  readable_id = readable_id.replace(/-+/g, "-");

  // Trim leading/trailing hyphens
  readable_id = readable_id.replace(/^-|-$/g, "");

  return readable_id;
}

/**
 * Generate a complete readable ID from a name.
 *
 * Combines the sanitized base with a random suffix, e.g.
 * `"finance-data-ab12x9"`.
 *
 * @param name - Human-readable name
 * @returns Full readable ID, or empty string if name is blank
 */
export function generateReadableId(name: string): string {
  const base = generateReadableIdBase(name);
  if (!base) return "";
  return `${base}-${generateRandomSuffix()}`;
}
