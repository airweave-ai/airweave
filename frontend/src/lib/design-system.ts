/**
 * Design System Constants for Airweave UI
 * Provides consistent styling values across all components
 */

export const DESIGN_SYSTEM = {
    // Button Heights
    buttons: {
        heights: {
            compact: 'h-6',     // 24px - for inline actions, small spaces
            secondary: 'h-8',   // 32px - for secondary actions, form controls
            primary: 'h-10',    // 40px - for primary actions, main CTAs
        },
        padding: {
            compact: 'px-2',
            secondary: 'px-3',
            primary: 'px-4',
        }
    },

    // Text Sizes
    typography: {
        sizes: {
            label: 'text-[10px]',        // Labels, captions, metadata
            body: 'text-xs',             // Body text, descriptions
            header: 'text-sm',           // Section headers, card titles
            title: 'text-base',          // Page titles, main headings
            display: 'text-lg',          // Large display text
        },
        weights: {
            normal: 'font-normal',
            medium: 'font-medium',
            semibold: 'font-semibold',
            bold: 'font-bold',
        },
        cases: {
            uppercase: 'uppercase',
            normal: 'normal-case',
        },
        tracking: {
            wide: 'tracking-wide',
            wider: 'tracking-wider',
            normal: 'tracking-normal',
        }
    },

    // Border Radius
    radius: {
        card: 'rounded-lg',      // 8px - for cards, panels
        button: 'rounded-md',    // 6px - for buttons, form controls
        input: 'rounded-md',     // 6px - for inputs, selects
        badge: 'rounded-md',     // 6px - for badges, chips
        modal: 'rounded-lg',     // 8px - for modals, dialogs
    },

    // Spacing Scale
    spacing: {
        gaps: {
            standard: 'gap-2',     // 8px - standard gap between related items
            section: 'gap-3',      // 12px - gap between sections
            major: 'gap-4',        // 16px - gap between major sections
            large: 'gap-6',        // 24px - large spacing
        },
        padding: {
            compact: 'p-3',        // 12px - compact card padding
            default: 'p-4',        // 16px - default card padding
            spacious: 'p-6',       // 24px - spacious card padding
        },
        margins: {
            section: 'space-y-4',  // 16px - between major sections
            items: 'space-y-2',    // 8px - between related items
            tight: 'space-y-1',    // 4px - tight spacing
        }
    },

    // Icon Sizes
    icons: {
        inline: 'h-3 w-3',       // 12px - inline with text
        button: 'h-4 w-4',       // 16px - in buttons, controls
        large: 'h-5 w-5',        // 20px - larger icons, standalone
        status: 'h-2.5 w-2.5',   // 10px - status indicators, dots
    },

    // Brand Colors (following existing theme structure)
    colors: {
        primary: {
            light: 'blue-600',
            dark: 'blue-400',
            hover: {
                light: 'blue-700',
                dark: 'blue-300',
            }
        },
        secondary: {
            light: 'gray-100',
            dark: 'gray-800',
            hover: {
                light: 'gray-200',
                dark: 'gray-700',
            }
        },
        accent: {
            light: 'indigo-600',
            dark: 'indigo-400',
        },
        success: {
            light: 'emerald-600',
            dark: 'emerald-400',
        },
        warning: {
            light: 'amber-600',
            dark: 'amber-400',
        },
        error: {
            light: 'red-600',
            dark: 'red-400',
        },
        border: {
            light: 'gray-200',
            dark: 'gray-700',
        },
        background: {
            light: 'white',
            dark: 'gray-900',
        },
        // Consistent semantic colors
        surface: {
            light: 'white',
            dark: 'gray-800',
            hover: {
                light: 'gray-50',
                dark: 'gray-700',
            }
        },
        muted: {
            light: 'gray-100',
            dark: 'gray-800',
            hover: {
                light: 'gray-200',
                dark: 'gray-700',
            }
        }
    },

    // Transitions
    transitions: {
        standard: 'transition-all duration-200',
        fast: 'transition-all duration-150',
        slow: 'transition-all duration-300',
    },

    // Shadows
    shadows: {
        card: 'shadow-sm',
        hover: 'hover:shadow-md',
        interactive: 'shadow-sm hover:shadow-md transition-shadow duration-200',
    },

    // Tooltip Styling
    tooltip: {
        content: 'max-w-[280px] p-2.5 rounded-md bg-gray-900 text-white border border-white/10 shadow-lg',
        title: 'text-sm font-semibold',
        description: 'text-xs text-white/90',
        link: 'inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15',
        divider: 'pt-2 mt-2 border-t border-white/10',
        arrow: 'fill-gray-900'
    }
} as const;

// Helper functions for common combinations
export const getButtonClasses = (variant: 'primary' | 'secondary' | 'compact', theme: 'light' | 'dark' = 'light') => {
    const base = `${DESIGN_SYSTEM.buttons.heights[variant]} ${DESIGN_SYSTEM.buttons.padding[variant]} ${DESIGN_SYSTEM.radius.button} ${DESIGN_SYSTEM.transitions.standard}`;

    switch (variant) {
        case 'primary':
            return `${base} bg-${DESIGN_SYSTEM.colors.primary[theme]} hover:bg-${DESIGN_SYSTEM.colors.primary.hover[theme]} text-white`;
        case 'secondary':
            return `${base} bg-${DESIGN_SYSTEM.colors.secondary[theme]} hover:bg-${DESIGN_SYSTEM.colors.secondary.hover[theme]}`;
        case 'compact':
            return `${base} bg-${DESIGN_SYSTEM.colors.secondary[theme]} hover:bg-${DESIGN_SYSTEM.colors.secondary.hover[theme]}`;
        default:
            return base;
    }
};

export const getCardClasses = (theme: 'light' | 'dark' = 'light') => {
    return `${DESIGN_SYSTEM.radius.card} ${DESIGN_SYSTEM.spacing.padding.default} ${DESIGN_SYSTEM.shadows.interactive} border border-${DESIGN_SYSTEM.colors.border[theme]} bg-${DESIGN_SYSTEM.colors.background[theme]}`;
};

export const getTextClasses = (variant: 'label' | 'body' | 'header' | 'title' | 'display', weight: 'normal' | 'medium' | 'semibold' | 'bold' = 'normal') => {
    return `${DESIGN_SYSTEM.typography.sizes[variant]} ${DESIGN_SYSTEM.typography.weights[weight]}`;
};
