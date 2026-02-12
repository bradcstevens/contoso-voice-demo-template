"use client";
// ---------------------------------------------------------------------------
// IncomingCallOverlay - displays a ringing call UI with accept/decline buttons
//
// Shown when the assistant's text response contains a "call me" trigger
// phrase. On accept, connects voice via the realtime manager. On decline,
// dismisses and continues text chat.
// ---------------------------------------------------------------------------

import { FiPhone, FiPhoneOff } from "react-icons/fi";
import { HiPhone } from "react-icons/hi2";
import styles from "./incoming-call.module.css";
import { AssistantName } from "@/store/chat";

interface IncomingCallOverlayProps {
  onAccept: () => void;
  onDecline: () => void;
}

const IncomingCallOverlay = ({
  onAccept,
  onDecline,
}: IncomingCallOverlayProps) => {
  return (
    <div className={styles.overlay} data-testid="incoming-call-overlay">
      {/* Ringing icon */}
      <div className={styles.ringContainer}>
        <HiPhone size={36} className={styles.ringIcon} />
      </div>

      {/* Caller info */}
      <div className={styles.callerInfo}>
        <div className={styles.callerName}>{AssistantName}</div>
        <div className={styles.callerLabel}>Incoming voice call...</div>
      </div>

      {/* Accept / Decline buttons */}
      <div className={styles.actions}>
        <button
          className={styles.actionButton}
          onClick={onAccept}
          title="Accept call"
          data-testid="accept-call-button"
        >
          <div className={styles.acceptCircle}>
            <FiPhone size={24} />
          </div>
          <span className={styles.actionLabel}>Accept</span>
        </button>

        <button
          className={styles.actionButton}
          onClick={onDecline}
          title="Decline call"
          data-testid="decline-call-button"
        >
          <div className={styles.declineCircle}>
            <FiPhoneOff size={24} />
          </div>
          <span className={styles.actionLabel}>Decline</span>
        </button>
      </div>
    </div>
  );
};

export default IncomingCallOverlay;
