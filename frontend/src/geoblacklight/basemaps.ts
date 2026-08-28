const basemaps = {
  openstreetmapStandard: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
    worldCopyJump: true,
  },
} as const;

export default basemaps;
