"use client";
import { HiMicrophone } from "react-icons/hi2";
import { FiMicOff } from "react-icons/fi";
import clsx from "clsx";
import styles from "./microphone-button.module.css";

interface MicrophoneButtonProps {
  isActive: boolean;
  disabled?: boolean;
  onClick: () => void;
}

const MicrophoneButton = ({
  isActive,
  disabled = false,
  onClick,
}: MicrophoneButtonProps) => {
  const title = isActive ? "End voice call" : "Start voice call";

  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      className={clsx(
        styles.micButton,
        isActive && styles.micButtonActive
      )}
      onClick={onClick}
    >
      {isActive ? (
        <FiMicOff size={24} className={styles.micIconActive} />
      ) : (
        <HiMicrophone size={24} className={styles.micIcon} />
      )}
    </button>
  );
};

export default MicrophoneButton;
