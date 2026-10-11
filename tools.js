/*
 * FlowerMoon tool list. To add a tool:
 *   1. put it in its own folder with an index.html (e.g. bending/index.html)
 *   2. add one entry below. Order here is the order on the home page.
 * icon: one of the keys in ICONS in index.html (cutter, paint, route, generic).
 * path can also be a full https:// address for a tool hosted elsewhere;
 * note (optional) is shown under the description.
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
  },
  {
    id: 'transport',
    name: 'Transport',
    path: 'https://flowermoon-transport.onrender.com/',
    icon: 'route',
    category: 'Logistics',
    language: 'EN',
    version: 'Web app',
    note: 'Hosted on Render: the first visit after a quiet period can take up to a minute.',
    description: 'Truck route planning with vehicle selection, plus destination site data: elevation, climate and humidity, seismic PGA, snow and wind zoning, Excel export.'
  }
];
