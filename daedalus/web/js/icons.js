// Line icons for each entity type (24x24 grid, stroke-based).

const P = {
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>',
  username: '<circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"/>',
  email: '<rect x="2.5" y="4.5" width="19" height="15" rx="2"/><path d="m3 7 9 6 9-6"/>',
  phone: '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
  account: '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="12" cy="10" r="3"/><path d="M7 18.5a5.5 5.5 0 0 1 10 0"/>',
  organization: '<path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16"/><path d="M15 9h4a1 1 0 0 1 1 1v11"/><path d="M2 21h20M8 8h3M8 12h3M8 16h3"/>',
  domain: '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.7 4 6 4 9.5s-1.4 6.8-4 9.5c-2.6-2.7-4-6-4-9.5s1.4-6.8 4-9.5z"/>',
  hostname: '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6"/>',
  ip: '<rect x="9" y="2.5" width="6" height="6" rx="1"/><rect x="2.5" y="15.5" width="6" height="6" rx="1"/><rect x="15.5" y="15.5" width="6" height="6" rx="1"/><path d="M5.5 15.5V12h13v3.5M12 12V8.5"/>',
  netblock: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  asn: '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H16a3.5 3.5 0 0 0 0-7H8a3.5 3.5 0 0 1 0-7h7.5"/>',
  url: '<path d="M10 13.5a4.5 4.5 0 0 0 6.8.5l2.7-2.7a4.5 4.5 0 0 0-6.4-6.4L11.6 6.4"/><path d="M14 10.5a4.5 4.5 0 0 0-6.8-.5l-2.7 2.7a4.5 4.5 0 0 0 6.4 6.4l1.5-1.5"/>',
  tracking_code: '<path d="M3 3v18h18"/><path d="M7.5 16v-4M12 16V8M16.5 16v-6.5"/>',
  location: '<path d="M19.5 10c0 5.5-7.5 11.5-7.5 11.5S4.5 15.5 4.5 10a7.5 7.5 0 0 1 15 0z"/><circle cx="12" cy="10" r="2.7"/>',
  crypto: '<circle cx="12" cy="12" r="9.5"/><path d="M9.5 7.5h4a2.2 2.2 0 0 1 0 4.5h-4zM9.5 12h4.6a2.25 2.25 0 0 1 0 4.5H9.5zM9.5 7.5v9M11 5.5v2M11 16.5v2M13.5 5.5v2M13.5 16.5v2"/>',
  hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  phrase: '<path d="M4 7V4.5h16V7M9 20h6M12 4.5V20"/>',
  breach: '<path d="M12 21.5s8-3.8 8-10V5l-8-3-8 3v6.5c0 6.2 8 10 8 10z"/><path d="M12 8v4.5M12 16h.01"/>',
  vulnerability: '<path d="M9 7.5V6a3 3 0 0 1 6 0v1.5"/><path d="M12 20.5c-3.3 0-6-2.7-6-6V11a3.5 3.5 0 0 1 3.5-3.5h5A3.5 3.5 0 0 1 18 11v3.5c0 3.3-2.7 6-6 6zM12 20.5v-8.5M6 13H2.5M21.5 13H18M6.3 17.5 3.5 19.5M17.7 17.5l2.8 2M6.5 9.5 4 7.5M17.5 9.5 20 7.5"/>',
};

export const ICON_NAMES = Object.keys(P);

export function iconSvg(type, color = "currentColor", size = 16, stroke = 1.8) {
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[type] || P.phrase}</svg>`;
}

const uriCache = new Map();
export function iconUri(type, color) {
  const key = `${type}|${color}`;
  if (!uriCache.has(key)) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="${color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${P[type] || P.phrase}</svg>`;
    uriCache.set(key, `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`);
  }
  return uriCache.get(key);
}
