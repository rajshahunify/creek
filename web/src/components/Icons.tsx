/** Inline SVG icons (24×24, currentColor), so the page needs no icon font or extra requests. */

import { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

const Svg = ({ children, ...p }: P) => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true" {...p}>{children}</svg>
);
const Line = ({ children, ...p }: P) => (
  <Svg fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...p}>
    {children}
  </Svg>
);

export const Play = (p: P) => <Svg {...p}><path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14Z" /></Svg>;
export const Pause = (p: P) => <Svg {...p}><rect x="6" y="4.5" width="4" height="15" rx="1.2" /><rect x="14" y="4.5" width="4" height="15" rx="1.2" /></Svg>;
export const Next = (p: P) => <Svg {...p}><path d="M5 6.2v11.6a1 1 0 0 0 1.53.85L15 13.2V17a1 1 0 0 0 2 0V7a1 1 0 0 0-2 0v3.8L6.53 5.35A1 1 0 0 0 5 6.2Z" /><rect x="17" y="6" width="2" height="12" rx="1" /></Svg>;
export const Prev = (p: P) => <Svg {...p} style={{ transform: "scaleX(-1)" }}><path d="M5 6.2v11.6a1 1 0 0 0 1.53.85L15 13.2V17a1 1 0 0 0 2 0V7a1 1 0 0 0-2 0v3.8L6.53 5.35A1 1 0 0 0 5 6.2Z" /><rect x="17" y="6" width="2" height="12" rx="1" /></Svg>;
export const Back5 = (p: P) => <Line {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><text x="12" y="15.5" fontSize="8" textAnchor="middle" fill="currentColor" stroke="none" fontWeight="700">5</text></Line>;
export const Fwd5 = (p: P) => <Line {...p}><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /><text x="12" y="15.5" fontSize="8" textAnchor="middle" fill="currentColor" stroke="none" fontWeight="700">5</text></Line>;
export const Volume = (p: P) => <Line {...p}><path d="M11 5 6 9H3v6h3l5 4V5Z" /><path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M18.5 5.5a9 9 0 0 1 0 13" /></Line>;
export const Muted = (p: P) => <Line {...p}><path d="M11 5 6 9H3v6h3l5 4V5Z" /><path d="m22 9-6 6M16 9l6 6" /></Line>;
export const Search = (p: P) => <Line {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Line>;
export const Bell = (p: P) => <Line {...p}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></Line>;
export const Keyboard = (p: P) => <Line {...p}><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M10 13h4M7 16h10" /></Line>;
export const Grip = (p: P) => <Svg {...p}><circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" /></Svg>;
export const More = (p: P) => <Svg {...p}><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></Svg>;
export const Close = (p: P) => <Line {...p}><path d="M18 6 6 18M6 6l12 12" /></Line>;
export const Sun = (p: P) => <Line {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></Line>;
export const Moon = (p: P) => <Line {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /></Line>;
export const Headphones = (p: P) => <Line {...p}><path d="M3 18v-6a9 9 0 0 1 18 0v6" /><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" /></Line>;
export const ListPlus = (p: P) => <Line {...p}><path d="M3 6h12M3 12h12M3 18h8M18 14v6M15 17h6" /></Line>;
export const PlayNext = (p: P) => <Line {...p}><path d="M3 6h9M3 12h9M3 18h9" /><path d="m16 9 5 3-5 3V9Z" fill="currentColor" /></Line>;
export const Zap = (p: P) => <Line {...p}><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z" /></Line>;
export const Trash = (p: P) => <Line {...p}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></Line>;
export const Up = (p: P) => <Line {...p}><path d="m18 15-6-6-6 6" /></Line>;
export const Down = (p: P) => <Line {...p}><path d="m6 9 6 6 6-6" /></Line>;
export const Users = (p: P) => <Line {...p}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></Line>;
export const Wave = (p: P) => <Line {...p}><path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0" /><path d="M2 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" opacity=".5" /><path d="M2 7c2-3 4-3 6 0s4 3 6 0 4-3 6 0" opacity=".5" /></Line>;
export const YouTube = (p: P) => <Svg {...p}><path d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12 31 31 0 0 0 1 16.8a3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-4.8 31 31 0 0 0-.5-4.8ZM9.8 15V9l5.7 3-5.7 3Z" /></Svg>;
export const Link = (p: P) => <Line {...p}><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" /><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" /></Line>;

// the dashboard's chrome
export const Menu = (p: P) => <Line {...p}><path d="M4 6h16M4 12h16M4 18h16" /></Line>;
export const Dashboard = (p: P) => <Line {...p}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></Line>;
export const Table = (p: P) => <Line {...p}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 9v12M15 9v12" /></Line>;
export const Music = (p: P) => <Line {...p}><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></Line>;
export const Shield = (p: P) => <Line {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /></Line>;
export const ChevronLeft = (p: P) => <Line {...p}><path d="m15 18-6-6 6-6" /></Line>;
export const ChevronRight = (p: P) => <Line {...p}><path d="m9 18 6-6-6-6" /></Line>;
export const Download = (p: P) => <Line {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></Line>;
export const Refresh = (p: P) => <Line {...p}><path d="M21 12a9 9 0 1 1-2.6-6.4L21 8" /><path d="M21 3v5h-5" /></Line>;
export const Command = (p: P) => <Line {...p}><path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" /></Line>;
export const Monitor = (p: P) => <Line {...p}><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></Line>;
export const Clock = (p: P) => <Line {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Line>;
export const Activity = (p: P) => <Line {...p}><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></Line>;
export const LogOut = (p: P) => <Line {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></Line>;
export const Sort = (p: P) => <Line {...p}><path d="m7 15 5 5 5-5M7 9l5-5 5 5" /></Line>;
