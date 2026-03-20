import React from 'react';

const SENTENCE_SPLIT_RE = /(?<=[.!?—])\s+/;
const MAX_ANIMATION_MS = 600;
const MIN_STAGGER_MS = 40;
const MAX_STAGGER_MS = 120;

interface StreamingSentencesProps {
    text: string;
    animate: boolean;
    className?: string;
}

/**
 * Renders text sentence-by-sentence with a staggered fade-in when `animate`
 * is true (used for the latest thinking event). When `animate` is false the
 * full text is rendered immediately (for past events or when a newer event
 * has already arrived).
 */
export const StreamingSentences: React.FC<StreamingSentencesProps> = ({
    text,
    animate,
    className,
}) => {
    const sentences = text.split(SENTENCE_SPLIT_RE).filter(Boolean);

    if (!animate || sentences.length <= 1) {
        return <span className={className}>{text}</span>;
    }

    const staggerMs = Math.max(
        MIN_STAGGER_MS,
        Math.min(MAX_STAGGER_MS, Math.round(MAX_ANIMATION_MS / sentences.length)),
    );

    return (
        <span className={className}>
            {sentences.map((sentence, j) => (
                <span
                    key={j}
                    className="animate-sentence-in"
                    style={{ animationDelay: `${j * staggerMs}ms` }}
                >
                    {sentence}
                    {j < sentences.length - 1 ? ' ' : ''}
                </span>
            ))}
        </span>
    );
};
