// Rune Icons by Nexvyn, https://www.runeicons.com (https://github.com/Nexvyn/runeicons), Apache-2.0.
// Copied from the repo at commit c5fef36ddaca68446dc10c78f55be684cca52c1c and converted to inline components (see THIRD_PARTY_NOTICES.md).
// Changes: attributes converted to JSX; outline and pixelated colours set to currentColor; glass ids namespaced per instance.
// To add or update an icon, copy its SVG from the repo and apply the same three changes.
import { useId } from "react";

type IconProps = { className?: string };

// public/glass-icons/Folder.svg
export function GlassFolder({ className }: IconProps) {
  const uid = `rune${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <mask id={`${uid}mask0_85_64`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="2" y="3" width="20" height="17">
      <path d="M2.75 5.75V17.25C2.75 18.3546 3.64543 19.25 4.75 19.25H19.25C20.3546 19.25 21.25 18.3546 21.25 17.25V8.75C21.25 7.64543 20.3546 6.75 19.25 6.75H13.0704C12.4017 6.75 11.7772 6.4158 11.4063 5.8594L10.5937 4.6406C10.2228 4.0842 9.59834 3.75 8.92963 3.75H4.75C3.64543 3.75 2.75 4.64543 2.75 5.75Z" fill="black"/>
      </mask>
      <g mask={`url(#${uid}mask0_85_64)`}>
      <g filter={`url(#${uid}filter0_f_85_64)`}>
      <ellipse cx="19.1777" cy="16.2113" rx="0.968208" ry="5.31726" transform="rotate(25.6915 19.1777 16.2113)" fill={`url(#${uid}paint0_linear_85_64)`}/>
      </g>
      </g>
      <path d="M2.75 5.75V17.25C2.75 18.3546 3.64543 19.25 4.75 19.25H19.25C20.3546 19.25 21.25 18.3546 21.25 17.25V8.75C21.25 7.64543 20.3546 6.75 19.25 6.75H13.0704C12.4017 6.75 11.7772 6.4158 11.4063 5.8594L10.5937 4.6406C10.2228 4.0842 9.59834 3.75 8.92963 3.75H4.75C3.64543 3.75 2.75 4.64543 2.75 5.75Z" fill={`url(#${uid}paint1_linear_85_64)`} stroke={`url(#${uid}paint2_linear_85_64)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <defs>
      <filter id={`${uid}filter0_f_85_64`} x="10.7119" y="5.40109" width="16.9316" height="21.6205" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="3" result="effect1_foregroundBlur_85_64"/>
      </filter>
      <linearGradient id={`${uid}paint0_linear_85_64`} x1="19.1777" y1="10.8941" x2="19.1777" y2="21.5286" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint1_linear_85_64`} x1="12" y1="3.75" x2="12" y2="19.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint2_linear_85_64`} x1="12" y1="3.75" x2="12" y2="19.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      </defs>
    </svg>
  );
}

// public/glass-icons/TrashCan.svg
export function GlassTrash({ className }: IconProps) {
  const uid = `rune${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <mask id={`${uid}mask0_85_600`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="4" y="6" width="16" height="16">
      <path d="M4.75 6.5L5.65512 19.3901C5.72868 20.4377 6.6 21.25 7.6502 21.25H16.3498C17.4 21.25 18.2713 20.4377 18.3449 19.3901L19.25 6.5" fill="black"/>
      </mask>
      <g mask={`url(#${uid}mask0_85_600)`}>
      <g filter={`url(#${uid}filter0_f_85_600)`}>
      <path d="M10.7998 11.3V17.05" stroke={`url(#${uid}paint0_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      </g>
      <g filter={`url(#${uid}filter1_f_85_600)`}>
      <path d="M14.9004 11.3V17.05" stroke={`url(#${uid}paint1_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      </g>
      <g filter={`url(#${uid}filter2_f_85_600)`}>
      <ellipse cx="17.5761" cy="16.8835" rx="0.968208" ry="4.84616" transform="rotate(20.1196 17.5761 16.8835)" fill={`url(#${uid}paint2_linear_85_600)`}/>
      </g>
      </g>
      <path d="M4.75 6.5L5.65512 19.3901C5.72868 20.4377 6.6 21.25 7.6502 21.25H16.3498C17.4 21.25 18.2713 20.4377 18.3449 19.3901L19.25 6.5" fill={`url(#${uid}paint3_linear_85_600)`}/>
      <path d="M4.75 6.5L5.65512 19.3901C5.72868 20.4377 6.6 21.25 7.6502 21.25H16.3498C17.4 21.25 18.2713 20.4377 18.3449 19.3901L19.25 6.5" stroke={`url(#${uid}paint4_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M10 10.5V16.25" stroke={`url(#${uid}paint5_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 10.5V16.25" stroke={`url(#${uid}paint6_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M3.25 5.75H20.75" stroke={`url(#${uid}paint7_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M8.52441 5.58289C8.7306 3.84652 10.2079 2.5 11.9998 2.5C13.7917 2.5 15.269 3.84652 15.4752 5.58289" stroke={`url(#${uid}paint8_linear_85_600)`} strokeLinecap="round" strokeLinejoin="round"/>
      <defs>
      <filter id={`${uid}filter0_f_85_600`} x="9.7998" y="10.3" width="2" height="7.75" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="0.25" result="effect1_foregroundBlur_85_600"/>
      </filter>
      <filter id={`${uid}filter1_f_85_600`} x="13.9004" y="10.3" width="2" height="7.75" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="0.25" result="effect1_foregroundBlur_85_600"/>
      </filter>
      <filter id={`${uid}filter2_f_85_600`} x="9.67676" y="6.32066" width="15.7988" height="21.1256" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="3" result="effect1_foregroundBlur_85_600"/>
      </filter>
      <linearGradient id={`${uid}paint0_linear_85_600`} x1="11.2998" y1="11.3" x2="11.2998" y2="17.05" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint1_linear_85_600`} x1="15.4004" y1="11.3" x2="15.4004" y2="17.05" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint2_linear_85_600`} x1="17.5761" y1="12.0373" x2="17.5761" y2="21.7296" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint3_linear_85_600`} x1="12" y1="6.5" x2="12" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint4_linear_85_600`} x1="12" y1="6.5" x2="12" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      <linearGradient id={`${uid}paint5_linear_85_600`} x1="10.5" y1="10.5" x2="10.5" y2="16.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint6_linear_85_600`} x1="14.5" y1="10.5" x2="14.5" y2="16.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint7_linear_85_600`} x1="12" y1="5.75" x2="12" y2="6.75" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint8_linear_85_600`} x1="11.9998" y1="2.5" x2="11.9998" y2="5.58289" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      </defs>
    </svg>
  );
}

// public/glass-icons/FileText.svg
export function GlassFileText({ className }: IconProps) {
  const uid = `rune${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <mask id={`${uid}mask0_151_188`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="4" y="2" width="16" height="20">
      <path d="M11.9216 2.75H6.75C5.64543 2.75 4.75 3.64543 4.75 4.75V19.25C4.75 20.3546 5.64543 21.25 6.75 21.25H17.25C18.3546 21.25 19.25 20.3546 19.25 19.25V10.0784C19.25 9.54799 19.0393 9.03929 18.6642 8.66421L13.3358 3.33579C12.9607 2.96071 12.452 2.75 11.9216 2.75Z" fill="black"/>
      </mask>
      <g mask={`url(#${uid}mask0_151_188)`}>
      <g filter={`url(#${uid}filter0_f_151_188)`}>
      <path d="M13 4V8C13 9.10457 13.8954 10 15 10H19" fill={`url(#${uid}paint0_linear_151_188)`}/>
      </g>
      <g filter={`url(#${uid}filter1_f_151_188)`}>
      <path d="M9 14H12.5" stroke={`url(#${uid}paint1_linear_151_188)`} strokeWidth="1.5" strokeLinecap="round"/>
      </g>
      <g filter={`url(#${uid}filter2_f_151_188)`}>
      <path d="M9 18H15.5" stroke={`url(#${uid}paint2_linear_151_188)`} strokeWidth="1.5" strokeLinecap="round"/>
      </g>
      </g>
      <path d="M11.9216 2.75H6.75C5.64543 2.75 4.75 3.64543 4.75 4.75V19.25C4.75 20.3546 5.64543 21.25 6.75 21.25H17.25C18.3546 21.25 19.25 20.3546 19.25 19.25V10.0784C19.25 9.54799 19.0393 9.03929 18.6642 8.66421L13.3358 3.33579C12.9607 2.96071 12.452 2.75 11.9216 2.75Z" fill={`url(#${uid}paint3_linear_151_188)`} stroke={`url(#${uid}paint4_linear_151_188)`} strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M12.75 3.25V7.25C12.75 8.35457 13.6454 9.25 14.75 9.25H18.75" fill={`url(#${uid}paint5_linear_151_188)`}/>
      <path d="M8.75 13.25H12.25" stroke={`url(#${uid}paint6_linear_151_188)`} strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M8.75 17.25H15.25" stroke={`url(#${uid}paint7_linear_151_188)`} strokeWidth="1.5" strokeLinecap="round"/>
      <defs>
      <filter id={`${uid}filter0_f_151_188`} x="12.5" y="3.5" width="7" height="7" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="0.25" result="effect1_foregroundBlur_151_188"/>
      </filter>
      <filter id={`${uid}filter1_f_151_188`} x="7.75" y="12.75" width="6" height="2.5" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="0.25" result="effect1_foregroundBlur_151_188"/>
      </filter>
      <filter id={`${uid}filter2_f_151_188`} x="7.75" y="16.75" width="9" height="2.5" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="0.25" result="effect1_foregroundBlur_151_188"/>
      </filter>
      <linearGradient id={`${uid}paint0_linear_151_188`} x1="16" y1="4" x2="16" y2="10" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint1_linear_151_188`} x1="10.75" y1="14" x2="10.75" y2="15" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint2_linear_151_188`} x1="12.25" y1="18" x2="12.25" y2="19" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint3_linear_151_188`} x1="12" y1="2.75" x2="12" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint4_linear_151_188`} x1="12" y1="2.75" x2="12" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      <linearGradient id={`${uid}paint5_linear_151_188`} x1="15.75" y1="3.25" x2="15.75" y2="9.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint6_linear_151_188`} x1="10.5" y1="13.25" x2="10.5" y2="14.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint7_linear_151_188`} x1="12" y1="17.25" x2="12" y2="18.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      </defs>
    </svg>
  );
}

// public/glass-icons/Microphone 2.svg
export function GlassMicrophone({ className }: IconProps) {
  const uid = `rune${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <mask id={`${uid}mask0_85_903`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="7" y="2" width="10" height="14">
      <path d="M12.0009 15.75C9.65377 15.75 7.75098 13.8472 7.75098 11.5V7C7.75098 4.65279 9.65377 2.75 12.0009 2.75C14.3481 2.75 16.2509 4.65279 16.2509 7V11.5C16.2509 13.8472 14.3481 15.75 12.0009 15.75Z" fill="black"/>
      </mask>
      <g mask={`url(#${uid}mask0_85_903)`}>
      <g filter={`url(#${uid}filter0_f_85_903)`}>
      <ellipse cx="14.2027" cy="14.3576" rx="0.859598" ry="3.20593" transform="rotate(59.7499 14.2027 14.3576)" fill={`url(#${uid}paint0_linear_85_903)`}/>
      </g>
      </g>
      <path d="M12.0009 15.75C9.65377 15.75 7.75098 13.8472 7.75098 11.5V7C7.75098 4.65279 9.65377 2.75 12.0009 2.75C14.3481 2.75 16.2509 4.65279 16.2509 7V11.5C16.2509 13.8472 14.3481 15.75 12.0009 15.75Z" fill={`url(#${uid}paint1_linear_85_903)`} stroke={`url(#${uid}paint2_linear_85_903)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12.0009 19C15.0764 19 17.7195 17.1489 18.8769 14.5M12.0009 19C8.92546 19 6.28233 17.1489 5.125 14.5M12.0009 19V21.25" stroke={`url(#${uid}paint3_linear_85_903)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <defs>
      <filter id={`${uid}filter0_f_85_903`} x="7.39941" y="8.57959" width="13.6064" height="11.5561" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="2" result="effect1_foregroundBlur_85_903"/>
      </filter>
      <linearGradient id={`${uid}paint0_linear_85_903`} x1="14.2027" y1="11.1517" x2="14.2027" y2="17.5636" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint1_linear_85_903`} x1="12.001" y1="2.75" x2="12.001" y2="15.75" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint2_linear_85_903`} x1="12.001" y1="2.75" x2="12.001" y2="15.75" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      <linearGradient id={`${uid}paint3_linear_85_903`} x1="12.0009" y1="14.5" x2="12.0009" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      </defs>
    </svg>
  );
}

// public/glass-icons/Lock 1.svg
export function GlassLock({ className }: IconProps) {
  const uid = `rune${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <mask id={`${uid}mask0_85_1241`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="4" y="9" width="16" height="13">
      <path d="M4.75 11.75C4.75 10.6454 5.64543 9.75 6.75 9.75H17.25C18.3546 9.75 19.25 10.6454 19.25 11.75V19.25C19.25 20.3546 18.3546 21.25 17.25 21.25H6.75C5.64543 21.25 4.75 20.3546 4.75 19.25V11.75Z" fill="black"/>
      </mask>
      <g mask={`url(#${uid}mask0_85_1241)`}>
      <g filter={`url(#${uid}filter0_f_85_1241)`}>
      <ellipse cx="16.0011" cy="20.3441" rx="0.968208" ry="3.20593" transform="rotate(49.5495 16.0011 20.3441)" fill={`url(#${uid}paint0_linear_85_1241)`}/>
      </g>
      <g filter={`url(#${uid}filter1_f_85_1241)`}>
      <path d="M12.7998 14.5V17.5" stroke={`url(#${uid}paint1_linear_85_1241)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </g>
      </g>
      <path d="M4.75 11.75C4.75 10.6454 5.64543 9.75 6.75 9.75H17.25C18.3546 9.75 19.25 10.6454 19.25 11.75V19.25C19.25 20.3546 18.3546 21.25 17.25 21.25H6.75C5.64543 21.25 4.75 20.3546 4.75 19.25V11.75Z" fill={`url(#${uid}paint2_linear_85_1241)`} stroke={`url(#${uid}paint3_linear_85_1241)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M16.25 9.75V7.25C16.25 4.90279 14.3472 3 12 3C9.65279 3 7.75 4.90279 7.75 7.25V9.75" stroke={`url(#${uid}paint4_linear_85_1241)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 14V17" stroke={`url(#${uid}paint5_linear_85_1241)`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <defs>
      <filter id={`${uid}filter0_f_85_1241`} x="9.48145" y="14.1369" width="13.0391" height="12.4145" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="2" result="effect1_foregroundBlur_85_1241"/>
      </filter>
      <filter id={`${uid}filter1_f_85_1241`} x="11.0498" y="12.75" width="3.5" height="6.5" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="0.5" result="effect1_foregroundBlur_85_1241"/>
      </filter>
      <linearGradient id={`${uid}paint0_linear_85_1241`} x1="16.0011" y1="17.1382" x2="16.0011" y2="23.55" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint1_linear_85_1241`} x1="13.2998" y1="14.5" x2="13.2998" y2="17.5" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint2_linear_85_1241`} x1="12" y1="9.75" x2="12" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint3_linear_85_1241`} x1="12" y1="9.75" x2="12" y2="21.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint4_linear_85_1241`} x1="12" y1="3" x2="12" y2="9.75" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint5_linear_85_1241`} x1="12.5" y1="14" x2="12.5" y2="17" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      </defs>
    </svg>
  );
}

// public/glass-icons/Pause 2.svg
export function GlassPause({ className }: IconProps) {
  const uid = `rune${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <mask id={`${uid}mask0_85_883`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="14" y="3" width="6" height="18">
      <path d="M14.75 5.75C14.75 4.64543 15.6454 3.75 16.75 3.75H17.25C18.3546 3.75 19.25 4.64543 19.25 5.75V18.25C19.25 19.3546 18.3546 20.25 17.25 20.25H16.75C15.6454 20.25 14.75 19.3546 14.75 18.25V5.75Z" fill="black"/>
      </mask>
      <g mask={`url(#${uid}mask0_85_883)`}>
      <g filter={`url(#${uid}filter0_f_85_883)`}>
      <ellipse cx="20.2746" cy="16.9554" rx="0.859598" ry="4.92115" transform="rotate(17.1832 20.2746 16.9554)" fill={`url(#${uid}paint0_linear_85_883)`}/>
      </g>
      </g>
      <mask id={`${uid}mask1_85_883`} style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="4" y="3" width="6" height="18">
      <path d="M4.75 5.75C4.75 4.64543 5.64543 3.75 6.75 3.75H7.25C8.35457 3.75 9.25 4.64543 9.25 5.75V18.25C9.25 19.3546 8.35457 20.25 7.25 20.25H6.75C5.64543 20.25 4.75 19.3546 4.75 18.25V5.75Z" fill={`url(#${uid}paint1_linear_85_883)`} stroke={`url(#${uid}paint2_linear_85_883)`} strokeLinejoin="round"/>
      </mask>
      <g mask={`url(#${uid}mask1_85_883)`}>
      <g filter={`url(#${uid}filter1_f_85_883)`}>
      <ellipse cx="8.81004" cy="16.9698" rx="1.07187" ry="4.92115" transform="rotate(21.6221 8.81004 16.9698)" fill={`url(#${uid}paint3_linear_85_883)`}/>
      </g>
      </g>
      <path d="M4.75 5.75C4.75 4.64543 5.64543 3.75 6.75 3.75H7.25C8.35457 3.75 9.25 4.64543 9.25 5.75V18.25C9.25 19.3546 8.35457 20.25 7.25 20.25H6.75C5.64543 20.25 4.75 19.3546 4.75 18.25V5.75Z" fill={`url(#${uid}paint4_linear_85_883)`} stroke={`url(#${uid}paint5_linear_85_883)`} strokeLinejoin="round"/>
      <path d="M14.75 5.75C14.75 4.64543 15.6454 3.75 16.75 3.75H17.25C18.3546 3.75 19.25 4.64543 19.25 5.75V18.25C19.25 19.3546 18.3546 20.25 17.25 20.25H16.75C15.6454 20.25 14.75 19.3546 14.75 18.25V5.75Z" fill={`url(#${uid}paint6_linear_85_883)`} stroke={`url(#${uid}paint7_linear_85_883)`} strokeLinejoin="round"/>
      <defs>
      <filter id={`${uid}filter0_f_85_883`} x="14.6045" y="8.24698" width="11.3398" height="17.4169" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="2" result="effect1_foregroundBlur_85_883"/>
      </filter>
      <filter id={`${uid}filter1_f_85_883`} x="2.74023" y="8.37769" width="12.1396" height="17.1843" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
      <feFlood floodOpacity="0" result="BackgroundImageFix"/>
      <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
      <feGaussianBlur stdDeviation="2" result="effect1_foregroundBlur_85_883"/>
      </filter>
      <linearGradient id={`${uid}paint0_linear_85_883`} x1="20.2746" y1="12.0343" x2="20.2746" y2="21.8766" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint1_linear_85_883`} x1="7" y1="3.75" x2="7" y2="20.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint2_linear_85_883`} x1="7" y1="3.75" x2="7" y2="20.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      <linearGradient id={`${uid}paint3_linear_85_883`} x1="8.81004" y1="12.0487" x2="8.81004" y2="21.891" gradientUnits="userSpaceOnUse">
      <stop stopColor="#575757"/>
      <stop offset="1" stopColor="#151515"/>
      </linearGradient>
      <linearGradient id={`${uid}paint4_linear_85_883`} x1="7" y1="3.75" x2="7" y2="20.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint5_linear_85_883`} x1="7" y1="3.75" x2="7" y2="20.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      <linearGradient id={`${uid}paint6_linear_85_883`} x1="17" y1="3.75" x2="17" y2="20.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="#E3E3E3" stopOpacity="0.6"/>
      <stop offset="1" stopColor="#BBBBC0" stopOpacity="0.6"/>
      </linearGradient>
      <linearGradient id={`${uid}paint7_linear_85_883`} x1="17" y1="3.75" x2="17" y2="20.25" gradientUnits="userSpaceOnUse">
      <stop stopColor="white"/>
      <stop offset="1" stopColor="white" stopOpacity="0"/>
      </linearGradient>
      </defs>
    </svg>
  );
}

// public/normal/senses/hand.svg
export function OutlineHand({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M18 11V6C18 5.46957 17.7893 4.96086 17.4142 4.58579C17.0391 4.21071 16.5304 4 16 4C15.4696 4 14.9609 4.21071 14.5858 4.58579C14.2107 4.96086 14 5.46957 14 6M14 10V4C14 3.46957 13.7893 2.96086 13.4142 2.58579C13.0391 2.21071 12.5304 2 12 2C11.4696 2 10.9609 2.21071 10.5858 2.58579C10.2107 2.96086 10 3.46957 10 4V6M10 6V10.5M10 6C10 5.46957 9.78929 4.96086 9.41421 4.58579C9.03914 4.21071 8.53043 4 8 4C7.46957 4 6.96086 4.21071 6.58579 4.58579C6.21071 4.96086 6 5.46957 6 6V14M18 8C18 7.46957 18.2107 6.96086 18.5858 6.58579C18.9608 6.21071 19.4695 6 20 6C20.5304 6 21.0391 6.21071 21.4142 6.58579C21.7893 6.96086 22 7.46957 22 8V14C22 16.1217 21.1571 18.1566 19.6568 19.6569C18.1565 21.1571 16.1217 22 14 22H12C9.19998 22 7.49998 21.14 6.00998 19.66L2.40998 16.06C2.06592 15.6789 1.88157 15.1802 1.89511 14.6669C1.90864 14.1537 2.11903 13.6653 2.4827 13.303C2.84638 12.9406 3.33548 12.7319 3.84875 12.7202C4.36202 12.7085 4.86014 12.8946 5.23998 13.24L6.99998 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/normal/senses/eye.svg
export function OutlineEye({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M2.06202 12.3481C1.97868 12.1236 1.97868 11.8766 2.06202 11.6521C2.87372 9.68397 4.25153 8.00116 6.02079 6.81701C7.79004 5.63287 9.87106 5.00073 12 5.00073C14.129 5.00073 16.21 5.63287 17.9792 6.81701C19.7485 8.00116 21.1263 9.68397 21.938 11.6521C22.0214 11.8766 22.0214 12.1236 21.938 12.3481C21.1263 14.3163 19.7485 15.9991 17.9792 17.1832C16.21 18.3674 14.129 18.9995 12 18.9995C9.87106 18.9995 7.79004 18.3674 6.02079 17.1832C4.25153 15.9991 2.87372 14.3163 2.06202 12.3481Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/normal/indicators/plus.svg
export function OutlinePlus({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M5 12H19M12 5V19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/normal/playback/play.svg
export function OutlinePlay({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M5 4.99998C4.9999 4.64807 5.09265 4.30237 5.26888 3.99777C5.44512 3.69318 5.69861 3.44047 6.00375 3.26518C6.30889 3.08988 6.65488 2.99821 7.00679 2.9994C7.3587 3.0006 7.70406 3.09462 8.008 3.27198L20.005 10.27C20.3078 10.4457 20.5591 10.6977 20.7339 11.001C20.9088 11.3042 21.0009 11.6481 21.0012 11.9981C21.0015 12.3482 20.91 12.6922 20.7357 12.9957C20.5614 13.2993 20.3105 13.5518 20.008 13.728L8.008 20.728C7.70406 20.9053 7.3587 20.9994 7.00679 21.0006C6.65488 21.0018 6.30889 20.9101 6.00375 20.7348C5.69861 20.5595 5.44512 20.3068 5.26888 20.0022C5.09265 19.6976 4.9999 19.3519 5 19V4.99998Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/normal/indicators/square-stop.svg
export function OutlineStop({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M19 3H5C3.89543 3 3 3.89543 3 5V19C3 20.1046 3.89543 21 5 21H19C20.1046 21 21 20.1046 21 19V5C21 3.89543 20.1046 3 19 3Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 9H10C9.44772 9 9 9.44772 9 10V14C9 14.5523 9.44772 15 10 15H14C14.5523 15 15 14.5523 15 14V10C15 9.44772 14.5523 9 14 9Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/normal/other/wifi.svg
export function OutlineWifi({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M12 20H12.01M2 8.82015C4.75011 6.36037 8.31034 5.00049 12 5.00049C15.6897 5.00049 19.2499 6.36037 22 8.82015M5 12.8591C6.86929 11.0268 9.38247 10.0005 12 10.0005C14.6175 10.0005 17.1307 11.0268 19 12.8591M8.5 16.4288C9.43464 15.5127 10.6912 14.9995 12 14.9995C13.3088 14.9995 14.5654 15.5127 15.5 16.4288" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/normal/gadgets/battery-full.svg
export function OutlineBattery({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M10 10V14M14 10V14M22 14V10M6 10V14M4 6H16C17.1046 6 18 6.89543 18 8V16C18 17.1046 17.1046 18 16 18H4C2.89543 18 2 17.1046 2 16V8C2 6.89543 2.89543 6 4 6Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// public/pixelated/senses/ear.svg
export function PixelEar({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 41 42" fill="none" aria-hidden="true" focusable="false">
      <path d="M27.1939 2.14258H15.4796V3.85686H27.1939V2.14258Z" fill="currentColor"/>
      <path d="M28.8674 3.85742H13.8062V5.57171H28.8674V3.85742Z" fill="currentColor"/>
      <path d="M18.8266 5.57129H12.1327V7.28557H18.8266V5.57129Z" fill="currentColor"/>
      <path d="M30.5408 5.57129H23.8469V7.28557H30.5408V5.57129Z" fill="currentColor"/>
      <path d="M15.4796 7.28613H10.4592V9.00042H15.4796V7.28613Z" fill="currentColor"/>
      <path d="M32.2143 7.28613H27.1938V9.00042H32.2143V7.28613Z" fill="currentColor"/>
      <path d="M13.8062 9H8.78577V10.7143H13.8062V9Z" fill="currentColor"/>
      <path d="M23.8469 9H18.8265V10.7143H23.8469V9Z" fill="currentColor"/>
      <path d="M33.8877 9H28.8673V10.7143H33.8877V9Z" fill="currentColor"/>
      <path d="M13.8062 10.7139H8.78577V12.4282H13.8062V10.7139Z" fill="currentColor"/>
      <path d="M25.5204 10.7139H17.1531V12.4282H25.5204V10.7139Z" fill="currentColor"/>
      <path d="M33.8877 10.7139H28.8673V12.4282H33.8877V10.7139Z" fill="currentColor"/>
      <path d="M12.1327 12.4287H8.78577V14.143H12.1327V12.4287Z" fill="currentColor"/>
      <path d="M20.5 12.4287H15.4796V14.143H20.5V12.4287Z" fill="currentColor"/>
      <path d="M27.1939 12.4287H22.1735V14.143H27.1939V12.4287Z" fill="currentColor"/>
      <path d="M33.8877 12.4287H30.5408V14.143H33.8877V12.4287Z" fill="currentColor"/>
      <path d="M12.1327 14.1426H8.78577V15.8569H12.1327V14.1426Z" fill="currentColor"/>
      <path d="M18.8266 14.1426H15.4796V15.8569H18.8266V14.1426Z" fill="currentColor"/>
      <path d="M27.1939 14.1426H23.8469V15.8569H27.1939V14.1426Z" fill="currentColor"/>
      <path d="M33.8877 14.1426H30.5408V15.8569H33.8877V14.1426Z" fill="currentColor"/>
      <path d="M20.5 15.8574H15.4796V17.5717H20.5V15.8574Z" fill="currentColor"/>
      <path d="M33.8877 15.8574H30.5408V17.5717H33.8877V15.8574Z" fill="currentColor"/>
      <path d="M22.1735 17.5713H17.1531V19.2856H22.1735V17.5713Z" fill="currentColor"/>
      <path d="M33.8877 17.5713H30.5408V19.2856H33.8877V17.5713Z" fill="currentColor"/>
      <path d="M22.1735 19.2861H18.8265V21.0004H22.1735V19.2861Z" fill="currentColor"/>
      <path d="M33.8877 19.2861H28.8673V21.0004H33.8877V19.2861Z" fill="currentColor"/>
      <path d="M22.1735 21H17.1531V22.7143H22.1735V21Z" fill="currentColor"/>
      <path d="M32.2143 21H27.1938V22.7143H32.2143V21Z" fill="currentColor"/>
      <path d="M20.5 22.7139H15.4796V24.4282H20.5V22.7139Z" fill="currentColor"/>
      <path d="M30.5408 22.7139H25.5204V24.4282H30.5408V22.7139Z" fill="currentColor"/>
      <path d="M18.8265 24.4287H17.1531V26.143H18.8265V24.4287Z" fill="currentColor"/>
      <path d="M28.8673 24.4287H23.8469V26.143H28.8673V24.4287Z" fill="currentColor"/>
      <path d="M27.1939 26.1426H22.1735V27.8569H27.1939V26.1426Z" fill="currentColor"/>
      <path d="M25.5204 27.8574H20.5V29.5717H25.5204V27.8574Z" fill="currentColor"/>
      <path d="M23.8469 29.5713H20.5V31.2856H23.8469V29.5713Z" fill="currentColor"/>
      <path d="M12.1327 31.2861H8.78577V33.0004H12.1327V31.2861Z" fill="currentColor"/>
      <path d="M23.8469 31.2861H20.5V33.0004H23.8469V31.2861Z" fill="currentColor"/>
      <path d="M12.1327 33H8.78577V34.7143H12.1327V33Z" fill="currentColor"/>
      <path d="M23.8469 33H20.5V34.7143H23.8469V33Z" fill="currentColor"/>
      <path d="M13.8062 34.7139H8.78577V36.4282H13.8062V34.7139Z" fill="currentColor"/>
      <path d="M23.8469 34.7139H18.8265V36.4282H23.8469V34.7139Z" fill="currentColor"/>
      <path d="M22.1735 36.4287H10.4592V38.143H22.1735V36.4287Z" fill="currentColor"/>
      <path d="M20.5 38.1426H12.1327V39.8569H20.5V38.1426Z" fill="currentColor"/>
    </svg>
  );
}

// public/pixelated/messaging/message-circle.svg
export function PixelMessage({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 40 41" fill="none" aria-hidden="true" focusable="false">
      <path d="M26.5306 2.0918H13.4694V3.76527H26.5306V2.0918Z" fill="currentColor"/>
      <path d="M29.7959 3.76562H10.2041V5.43909H29.7959V3.76562Z" fill="currentColor"/>
      <path d="M16.7347 5.43848H8.57141V7.11195H16.7347V5.43848Z" fill="currentColor"/>
      <path d="M31.4286 5.43848H23.2653V7.11195H31.4286V5.43848Z" fill="currentColor"/>
      <path d="M11.8367 7.1123H6.93878V8.78577H11.8367V7.1123Z" fill="currentColor"/>
      <path d="M33.0612 7.1123H28.1633V8.78577H33.0612V7.1123Z" fill="currentColor"/>
      <path d="M10.2041 8.78613H5.30615V10.4596H10.2041V8.78613Z" fill="currentColor"/>
      <path d="M34.6939 8.78613H29.7959V10.4596H34.6939V8.78613Z" fill="currentColor"/>
      <path d="M8.57142 10.459H3.67346V12.1325H8.57142V10.459Z" fill="currentColor"/>
      <path d="M36.3265 10.459H31.4286V12.1325H36.3265V10.459Z" fill="currentColor"/>
      <path d="M6.93877 12.1328H3.67346V13.8063H6.93877V12.1328Z" fill="currentColor"/>
      <path d="M36.3265 12.1328H33.0612V13.8063H36.3265V12.1328Z" fill="currentColor"/>
      <path d="M6.93879 13.8057H2.04083V15.4791H6.93879V13.8057Z" fill="currentColor"/>
      <path d="M37.9592 13.8057H33.0612V15.4791H37.9592V13.8057Z" fill="currentColor"/>
      <path d="M6.93879 15.4795H2.04083V17.153H6.93879V15.4795Z" fill="currentColor"/>
      <path d="M37.9592 15.4795H33.0612V17.153H37.9592V15.4795Z" fill="currentColor"/>
      <path d="M5.30614 17.1533H2.04083V18.8268H5.30614V17.1533Z" fill="currentColor"/>
      <path d="M37.9592 17.1533H34.6938V18.8268H37.9592V17.1533Z" fill="currentColor"/>
      <path d="M5.30614 18.8262H2.04083V20.4996H5.30614V18.8262Z" fill="currentColor"/>
      <path d="M37.9592 18.8262H34.6938V20.4996H37.9592V18.8262Z" fill="currentColor"/>
      <path d="M5.30614 20.5H2.04083V22.1735H5.30614V20.5Z" fill="currentColor"/>
      <path d="M37.9592 20.5H34.6938V22.1735H37.9592V20.5Z" fill="currentColor"/>
      <path d="M5.30614 22.1738H2.04083V23.8473H5.30614V22.1738Z" fill="currentColor"/>
      <path d="M37.9592 22.1738H34.6938V23.8473H37.9592V22.1738Z" fill="currentColor"/>
      <path d="M6.93879 23.8467H2.04083V25.5201H6.93879V23.8467Z" fill="currentColor"/>
      <path d="M37.9592 23.8467H33.0612V25.5201H37.9592V23.8467Z" fill="currentColor"/>
      <path d="M6.93879 25.5205H2.04083V27.194H6.93879V25.5205Z" fill="currentColor"/>
      <path d="M37.9592 25.5205H33.0612V27.194H37.9592V25.5205Z" fill="currentColor"/>
      <path d="M6.93877 27.1943H3.67346V28.8678H6.93877V27.1943Z" fill="currentColor"/>
      <path d="M36.3265 27.1943H33.0612V28.8678H36.3265V27.1943Z" fill="currentColor"/>
      <path d="M6.93877 28.8672H3.67346V30.5407H6.93877V28.8672Z" fill="currentColor"/>
      <path d="M36.3265 28.8672H31.4286V30.5407H36.3265V28.8672Z" fill="currentColor"/>
      <path d="M6.93877 30.541H3.67346V32.2145H6.93877V30.541Z" fill="currentColor"/>
      <path d="M34.6939 30.541H29.7959V32.2145H34.6939V30.541Z" fill="currentColor"/>
      <path d="M6.93879 32.2139H2.04083V33.8873H6.93879V32.2139Z" fill="currentColor"/>
      <path d="M33.0612 32.2139H28.1633V33.8873H33.0612V32.2139Z" fill="currentColor"/>
      <path d="M5.30614 33.8877H2.04083V35.5612H5.30614V33.8877Z" fill="currentColor"/>
      <path d="M16.7347 33.8877H6.93878V35.5612H16.7347V33.8877Z" fill="currentColor"/>
      <path d="M31.4286 33.8877H23.2653V35.5612H31.4286V33.8877Z" fill="currentColor"/>
      <path d="M29.7959 35.5615H2.04083V37.235H29.7959V35.5615Z" fill="currentColor"/>
      <path d="M10.2041 37.2344H3.67346V38.9078H10.2041V37.2344Z" fill="currentColor"/>
      <path d="M26.5306 37.2344H13.4694V38.9078H26.5306V37.2344Z" fill="currentColor"/>
    </svg>
  );
}
