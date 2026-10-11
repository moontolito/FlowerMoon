/*
 * FlowerMoon tool list. To add a tool:
 *   1. put it in its own folder with an index.html (e.g. bending/index.html)
 *   2. add one entry below. Order here is the order on the home page.
 * icon: one of the keys in ICONS in index.html (cutter, paint, generic).
 */
window.FLOWERMOON_TOOLS = [
  {
    id: 'flowercutter',
    name: 'FlowerCutter',
    path: 'flowercutter/',
    icon: 'cutter',
    category: 'Sheet metal',
    language: 'EN',
    version: '1.0.0',
    description: 'Rectangular sheet cutting and layout planning: stock sizes, parts, kerf and trims, optimised layouts, PDF and Excel export.'
  },
  {
    id: 'painting',
    name: 'Painting',
    path: 'painting/',
    icon: 'paint',
    category: 'Coating',
    language: 'RO',
    version: 'v18',
    description: 'Paint quantity and cost calculator: exterior and interior corrosivity class (C2–C5), RAL finish colour, coating layers and packs. Enter your own €/L prices for the order total.'
  }
];
