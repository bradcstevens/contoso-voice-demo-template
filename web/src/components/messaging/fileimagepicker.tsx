import { useRef } from "react";
import { IoCameraOutline } from "react-icons/io5";
import { readAndCacheFile } from "@/store/images";

type Props = {
  setCurrentImage: (image: string) => void;
};

const FileImagePicker = ({ setCurrentImage }: Props) => {
  /** refs */
  const fileInput = useRef<HTMLInputElement>(null);


  /** Events */
  const activateFileInput = () => {
    if (fileInput.current) {
      fileInput.current.click();
    }
  };



  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    readAndCacheFile(file).then((data) => {
      if (!data) return;
      setCurrentImage(data);
      e.target.value = "";
    });
  };

  return (
    <>
      <IoCameraOutline
        size={18}
        style={{ color: "var(--color-zinc-500)", flexShrink: 0 }}
        onClick={activateFileInput}
      />
      <input
        type="file"
        className="hidden"
        accept="image/*"
        ref={fileInput}
        onChange={handleFileChange}
      />
    </>
  );
};

export default FileImagePicker;
