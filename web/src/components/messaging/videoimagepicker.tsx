import { FormEvent, useEffect, useRef, useState } from "react";
import { HiOutlineVideoCamera } from "react-icons/hi2";
import styles from "./videoimagepicker.module.css";
import { GrClose } from "react-icons/gr";
import { readAndCacheVideoFrame } from "@/store/images";

type Props = {
  setCurrentImage: (image: string) => void;
};

const VideoImagePicker = ({ setCurrentImage }: Props) => {
  const [show, setShow] = useState(false);
  const [showCamera, setShowCamera] = useState<boolean>(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<MediaDeviceInfo>();
  const videoRef = useRef<HTMLVideoElement>(null);

  const getDevices = async (requestPermission = false): Promise<MediaDeviceInfo[] | null> => {
    try {
      if (requestPermission) {
        // Only request permission when explicitly needed
        await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter((device) => device.kind === "videoinput");
    } catch (err: any) {
      console.error("Error accessing camera devices:", err);
      if (err instanceof DOMException) {
        if (
          err.name === "NotAllowedError" ||
          err.name === "PermissionDeniedError"
        ) {
          alert("Please allow camera access to use this feature.");
        }
      } else {
        alert("Error accessing camera.");
      }
      return null;
    }
  };

  const getSelectedDevice = async (): Promise<MediaDeviceInfo | null> => {
    const devices = await getDevices();
    if (!devices) return null;

    const device = localStorage.getItem("selected-video-device");

    if (device) {
      const parsedDevice = JSON.parse(device);
      const dvc = devices?.find((d) => d.deviceId === parsedDevice.deviceId);
      if (dvc) {
        return dvc;
      } else {
        // remove selected device if not found (bad entry)
        localStorage.removeItem("selected-video-device");
        return devices?.[0];
      }
    } else {
      return devices?.[0];
    }
  };

  const startVideo = async (deviceId: string) => {
    // Only start video in browser environment
    if (typeof window === 'undefined') {
      console.warn('Video start skipped: not in browser environment');
      return;
    }
    
    if (videoRef.current) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: deviceId } },
        });
        videoRef.current.disablePictureInPicture = true;
        videoRef.current.srcObject = stream;
        setShowCamera(true);
      } catch (err: any) {
        console.error("Error accessing camera:", err);
        let errorMessage = "Error accessing camera.";
        if (err.name === "NotAllowedError") {
          errorMessage = "Camera access denied. Please allow camera permissions to use this feature.";
        } else if (err.name === "NotFoundError") {
          errorMessage = "No camera found. Please connect a camera to use this feature.";
        } else if (err.name === "NotReadableError") {
          errorMessage = "Camera is already in use by another application.";
        }
        alert(errorMessage);
        videoRef.current.srcObject = null;
        setShowCamera(false);
      }
    }
  };

  const showVideo = async () => {
    // Request permission when user actually wants to use camera
    const devices = await getDevices(true);
    if (!devices) {
      setShow(false);
      return;
    }

    const device = await getSelectedDevice();
    if (!device) {
      setShow(false);
      return;
    }

    setDevices(devices);
    setSelectedDevice(device);
    setShow(true);
  };

  const stopVideo = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
      setShowCamera(false);
    }
  };

  const handleVideoClick = () => {
    if (videoRef.current) {
      readAndCacheVideoFrame(videoRef.current!).then((data) => {
        if (!data) return;
        setCurrentImage(data);
        stopVideo();
        setShow(false);
      });
    }
  };

  const handleClose = () => {
    stopVideo();
    setShow(false);
  };

  useEffect(() => {
    if (selectedDevice) {
      startVideo(selectedDevice.deviceId);
      localStorage.setItem(
        "selected-video-device",
        JSON.stringify({ deviceId: selectedDevice.deviceId })
      );
    }
  }, [selectedDevice]);

  // Cleanup effect
  useEffect(() => {
    return () => {
      stopVideo();
    };
  }, []);

  return (
    <>
      {show && (
        <div className={styles.videooverlay}>
          <div className={styles.videoimagepicker}>
            <div className={styles.videobox}>
              <div className={styles.header}>
                <select
                  id="device"
                  name="device"
                  className={styles.mediaselect}
                  value={selectedDevice?.deviceId}
                  title="Select a device"
                  onInput={(e: FormEvent<HTMLSelectElement>) =>
                    setSelectedDevice(
                      devices.find((d) => d.deviceId === e.currentTarget.value)
                    )
                  }
                >
                  {devices.map((device) => {
                    return (
                      <option key={device.deviceId} value={device.deviceId}>
                        {device.label}
                      </option>
                    );
                  })}
                </select>
                {showCamera && (
                  <div className="button" onClick={() => handleVideoClick()}>
                    <HiOutlineVideoCamera size={24} className="buttonIcon" />
                  </div>
                )}
                <button className="button" onClick={handleClose}>
                  <GrClose size={24} className="buttonIcon" />
                </button>
              </div>
              <div className={styles.video}>
                <video
                  ref={videoRef}
                  autoPlay={true}
                  className={styles.videoelement}
                  title="Click to take a picture"
                  onClick={() => handleVideoClick()}
                ></video>
              </div>
            </div>
          </div>
        </div>
      )}
      <button
        title="Use Video Image"
        className={"button"}
        onClick={() => showVideo()}
      >
        <HiOutlineVideoCamera className={"buttonIcon"} />
      </button>
    </>
  );
};

export default VideoImagePicker;
