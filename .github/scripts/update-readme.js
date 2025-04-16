const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const APPS_DIR = 'frontend/src/components/icons/apps';
const README_PATH = 'README.md';
const GRID_START_MARKER = '<!-- START_APP_GRID -->';
const GRID_END_MARKER = '<!-- END_APP_GRID -->';
const ICON_SIZE = 40;
const GRID_COLUMNS = 8;

async function generateAppGrid() {
  const files = fs.readdirSync(APPS_DIR)
    .filter(file => file.endsWith('.svg'))
    // Exclude light versions of icons
    .filter(file => !file.endsWith('-light.svg'))
    .sort();

  const rows = [];
  let currentRow = [];

  for (const file of files) {
    const name = path.basename(file, '.svg')
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');

    currentRow.push(`<img src="frontend/src/components/icons/apps/${file}" alt="${name}" width="${ICON_SIZE}" height="${ICON_SIZE}" style="margin: 4px; padding: 2px;" />`);

    if (currentRow.length === GRID_COLUMNS) {
      rows.push(currentRow);
      currentRow = [];
    }
  }

  if (currentRow.length > 0) {
    // Center the last row if it's not full
    const padding = Math.floor((GRID_COLUMNS - currentRow.length) / 2);
    const paddedRow = [
      ...Array(padding).fill(`<span style="width: ${ICON_SIZE}px; display: inline-block; margin: 4px;"></span>`),
      ...currentRow,
    ];
    rows.push(paddedRow);
  }

  // Wrap the grid in a centered container with padding
  return `<p align="center">\n  <div style="display: inline-block; text-align: center; padding: 4px;">\n    ${
    rows.map(row => row.join('')).join('\n    ')
  }\n  </div>\n</p>`;
}

async function updateReadme() {
  const readme = fs.readFileSync(README_PATH, 'utf8');
  const startIndex = readme.indexOf(GRID_START_MARKER);
  const endIndex = readme.indexOf(GRID_END_MARKER);

  if (startIndex === -1 || endIndex === -1) {
    console.error('Grid markers not found in README');
    return;
  }

  const existingGrid = readme.substring(startIndex + GRID_START_MARKER.length, endIndex).trim();
  const newGrid = await generateAppGrid();

  if (existingGrid === newGrid) {
    console.log('README is already up to date');
    return;
  }

  const updatedReadme =
    readme.substring(0, startIndex + GRID_START_MARKER.length) +
    '\n\n' + newGrid + '\n\n' +
    readme.substring(endIndex);

  fs.writeFileSync(README_PATH, updatedReadme);
  console.log('README updated successfully');
}

updateReadme().catch(console.error);
