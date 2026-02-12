"use client";
// ---------------------------------------------------------------------------
// HangupButton - red phone button to end an active voice call
//
// Visible only when voice is connected. On click, calls the provided onHangup
// callback which tears down the realtime WebSocket, stops audio, and returns
// the user to text-only chat mode.
// ---------------------------------------------------------------------------

import { FiPhoneOff } from "react-icons/fi";
import styles from "./hangup-button.module.css";

interface HangupButtonProps {
  onClick: () => void;
}

const HangupButton = ({ onClick }: HangupButtonProps) => {
  return (
    <button
      type="button"
      title="End voice call"
      className={styles.hangupButton}
      onClick={onClick}
      data-testid="hangup-button"
    >
      <FiPhoneOff size={24} className={styles.hangupIcon} />
    </button>
  );
};

export default HangupButton;
