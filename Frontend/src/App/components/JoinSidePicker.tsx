import { useContext, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { GameContext } from "../../Context/GameContext";

interface JoinSidePickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const sideButtonClass =
  "flex-1 py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm shadow-md hover:shadow-lg active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100";

export function JoinSidePicker({ open, onOpenChange }: JoinSidePickerProps) {
  const { joinGame, joining, joinError, hasJoined } = useContext(GameContext);

  useEffect(() => {
    if (open && hasJoined) {
      onOpenChange(false);
    }
  }, [open, hasJoined, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex h-[200px] w-[300px] max-w-[300px] flex-col justify-between gap-3 p-5 [&>button]:hidden"
      >
        <DialogHeader className="text-center sm:text-center">
          <DialogTitle className="font-[Alexandria] text-lg font-bold text-[#3c3c3c]">
            Heads or Tails?
          </DialogTitle>
          <DialogDescription className="sr-only">
            Choose heads or tails to join the live round.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-3">
          <button
            type="button"
            disabled={joining}
            onClick={() => void joinGame("heads")}
            className={sideButtonClass}
          >
            Heads
          </button>
          <button
            type="button"
            disabled={joining}
            onClick={() => void joinGame("tails")}
            className={sideButtonClass}
          >
            Tails
          </button>
        </div>

        <p className="min-h-[1rem] text-center text-xs font-[Alexandria]">
          {joining ? (
            <span className="text-gray-400">Joining…</span>
          ) : joinError ? (
            <span className="text-red-500">{joinError}</span>
          ) : null}
        </p>
      </DialogContent>
    </Dialog>
  );
}
