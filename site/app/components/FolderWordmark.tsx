// A giant "zoya" built from drawn Finder folders, like heyclicky's footer. Decorative (the parent is aria-hidden).

const LETTERS: Record<string, readonly string[]> = {
  z: ["#####", "...#.", "..#..", ".#...", "#....", "#####"],
  o: [".###.", "#...#", "#...#", "#...#", "#...#", ".###."],
  y: ["#...#", "#...#", ".####", "....#", "...#.", "###.."],
  a: [".###.", "....#", ".####", "#...#", "#..##", ".##.#"],
};

const WORD = "zoya";
const CELL = 10;
const LETTER_WIDTH = 5;
const LETTER_STEP = LETTER_WIDTH + 1;
const ROWS = 6;
// Folders are a little larger than a cell so neighbours overlap into solid, chunky letters.
const FOLDER_WIDTH = 11.5;
const FOLDER_HEIGHT = 9.2;

// Small deterministic offsets so the stack looks hand-placed, not printed.
function jitter(seed: number): number {
  return ((seed % 5) - 2) * 0.3;
}

const CELLS = [...WORD].flatMap((letter, li) =>
  LETTERS[letter].flatMap((row, r) =>
    [...row].flatMap((mark, c) =>
      mark === "#"
        ? [{ x: (li * LETTER_STEP + c) * CELL + jitter(li * 7 + r * 3 + c * 5), y: r * CELL + jitter(li + r * 5 + c * 3) }]
        : [],
    ),
  ),
);

const WIDTH = (WORD.length * LETTER_STEP - 1) * CELL;

export function FolderWordmark() {
  return (
    <svg className="folder-wordmark" viewBox={`-1 -1 ${WIDTH + 2} ${ROWS * CELL + 2}`} focusable="false">
      <defs>
        <symbol id="wordmark-folder" viewBox="0 0 64 50">
          <path fill="#4aa8e8" d="M4 8a4 4 0 0 1 4-4h15.5a4 4 0 0 1 2.8 1.2L31 10h25a4 4 0 0 1 4 4v28a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" />
          <path fill="#79c4f5" d="M4 17a3 3 0 0 1 3-3h50a3 3 0 0 1 3 3v25a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" />
          <path fill="#a9dcfb" d="M7 14h50a3 3 0 0 1 3 3v1.5H4V17a3 3 0 0 1 3-3z" />
        </symbol>
      </defs>
      {CELLS.map(({ x, y }) => (
        <use key={`${x}-${y}`} href="#wordmark-folder" x={x} y={y} width={FOLDER_WIDTH} height={FOLDER_HEIGHT} />
      ))}
    </svg>
  );
}
