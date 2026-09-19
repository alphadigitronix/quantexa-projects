"""Computer Vision module for traffic surveillance and vehicle inflow detection.

Primary engine : YOLOv8n (ultralytics) pre-trained on COCO, zero extra training needed.
Fallback engine: Classical OpenCV pipeline (road-line-resistant, solidity-filtered).

COCO vehicle classes detected by YOLO:
    2  car  |  3  motorcycle  |  5  bus  |  7  truck
"""

from __future__ import annotations
import logging, os, tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2, numpy as np

logger = logging.getLogger(__name__)

VEHICLE_CLASS_IDS: set = {2, 3, 5, 7}
YOLO_MODEL_NAME   = "yolov8n.pt"
YOLO_CONF         = 0.30
YOLO_IOU          = 0.45

_yolo_model     = None
_yolo_available = None


def _get_yolo():
    global _yolo_model, _yolo_available
    if _yolo_available is False:
        return None
    if _yolo_model is not None:
        return _yolo_model
    try:
        from ultralytics import YOLO
        model_path = Path.home() / ".cache" / "ultralytics" / YOLO_MODEL_NAME
        _yolo_model = YOLO(str(model_path) if model_path.exists() else YOLO_MODEL_NAME)
        _yolo_model.predict(np.zeros((64,64,3), dtype=np.uint8), verbose=False, conf=YOLO_CONF)
        _yolo_available = True
        logger.info("YOLOv8 loaded OK")
        return _yolo_model
    except Exception as exc:
        logger.warning("YOLO unavailable (%s), using classical CV", exc)
        _yolo_available = False
        return None


# ─── Classical CV fallback helpers ────────────────────────────────────────────

def _clahe_grey(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.createCLAHE(2.5, (8,8)).apply(g)

def _road_mask(img):
    sat  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:,:,1]
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap  = cv2.GaussianBlur(np.abs(cv2.Laplacian(grey.astype(np.float32), cv2.CV_32F)).astype(np.uint8), (15,15), 0)
    lap  = cv2.normalize(lap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    comb = cv2.addWeighted(sat, 0.55, lap, 0.45, 0)
    _, m = cv2.threshold(comb, 22, 255, cv2.THRESH_BINARY)
    return m

def _stripe_kill(mask):
    hk = cv2.getStructuringElement(cv2.MORPH_RECT,(1,9))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT,(9,1))
    return cv2.bitwise_or(cv2.morphologyEx(mask,cv2.MORPH_OPEN,hk), cv2.morphologyEx(mask,cv2.MORPH_OPEN,vk))

def _iou(a,b):
    ix = max(0, min(a[0]+a[2],b[0]+b[2]) - max(a[0],b[0]))
    iy = max(0, min(a[1]+a[3],b[1]+b[3]) - max(a[1],b[1]))
    inter = ix*iy
    union = a[2]*a[3] + b[2]*b[3] - inter
    return inter/union if union>0 else 0.0

def _classical_detect(img, min_area=380):
    h,w = img.shape[:2]
    sc  = min(1.0, 1024/w)
    wrk = cv2.resize(img,(int(w*sc),int(h*sc)),interpolation=cv2.INTER_AREA) if sc<1 else img.copy()
    dn  = cv2.fastNlMeansDenoisingColored(wrk,None,6,6,7,21)
    gr  = _clahe_grey(dn)
    rm  = _road_mask(dn)
    ed  = cv2.Canny(cv2.GaussianBlur(gr,(5,5),0), 35, 90)
    fu  = cv2.bitwise_and(ed, rm)
    cl  = cv2.morphologyEx(fu,  cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT,(9,5)), iterations=2)
    di  = cv2.dilate(cl, cv2.getStructuringElement(cv2.MORPH_RECT,(7,5)))
    cl2 = _stripe_kill(di)
    cnts,_ = cv2.findContours(cl2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw = []
    for cnt in cnts:
        a_s = cv2.contourArea(cnt)
        a_o = a_s/(sc*sc)
        if a_o < min_area or a_o > h*w*0.55: continue
        xw,yw,ww,hw = cv2.boundingRect(cnt)
        x,y = int(xw/sc),int(yw/sc)
        bw,bh = max(1,int(ww/sc)), max(1,int(hw/sc))
        if bw<22 or bh<16: continue
        ar = bw/bh
        if not (0.40<=ar<=4.20): continue
        ha = cv2.contourArea(cv2.convexHull(cnt))
        sol = a_s/ha if ha>0 else 0
        if sol<0.45: continue
        ars = max(0.5, 1-abs(ar-1.5)/5)
        ext = a_s/max(1,ww*hw)
        cf  = min(0.97, max(0.50, (sol*0.5+ars*0.3+ext*0.2)*1.15))
        raw.append([x,y,bw,bh,cf])
    if not raw: return []
    try:
        idx = cv2.dnn.NMSBoxes([[b[0],b[1],b[2],b[3]] for b in raw],[float(b[4]) for b in raw],0.50,0.35)
        sel = [int(i) for i in idx] if len(idx)>0 else []
    except Exception:
        raw.sort(key=lambda b:-b[4]); kept=[]
        for b in raw:
            if not any(_iou(b[:4],k[:4])>0.35 for k in kept): kept.append(b)
        sel=list(range(len(kept))); raw=kept
    out=[]
    for i in sel:
        b=raw[i]
        out.append({"id":len(out)+1,"x":b[0],"y":b[1],"w":b[2],"h":b[3],"confidence":round(b[4],2),"class_name":"vehicle"})
    return out


# ─── Annotation ───────────────────────────────────────────────────────────────

_CLASS_COLORS = {
    "car":        (255, 200,   0),
    "motorcycle": (  0, 220, 255),
    "bus":        (  0,  80, 255),
    "truck":      (  0, 255, 140),
    "vehicle":    (255, 229,   0),
}

def _annotate(img, detections, engine):
    out = img.copy()
    for det in detections:
        x,y,w,h = det["x"],det["y"],det["w"],det["h"]
        col  = _CLASS_COLORS.get(det.get("class_name","vehicle"), (255,229,0))
        conf = int(det["confidence"]*100)
        cv2.rectangle(out,(x,y),(x+w,y+h),col,2)
        ll = min(14, min(w,h)//3)
        for px,py in [(x,y),(x+w,y),(x,y+h),(x+w,y+h)]:
            sx=1 if px==x else -1; sy=1 if py==y else -1
            cv2.line(out,(px,py),(px+sx*ll,py),col,3)
            cv2.line(out,(px,py),(px,py+sy*ll),col,3)
        lbl = f"{det.get('class_name','VEH').upper()} #{det['id']}  {conf}%"
        (tw,th),_ = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.40,1)
        cv2.rectangle(out,(x,max(0,y-th-8)),(x+tw+8,max(0,y)),(15,23,42),-1)
        cv2.rectangle(out,(x,max(0,y-th-8)),(x+tw+8,max(0,y)),col,1)
        cv2.putText(out,lbl,(x+4,max(0,y-4)),cv2.FONT_HERSHEY_SIMPLEX,0.40,(0,229,255),1,cv2.LINE_AA)
    n   = len(detections)
    hud = f"QUANTUM TRAFFIC BRAIN  [{engine}]  |  {n} VEHICLE{'S' if n!=1 else ''} DETECTED"
    x2  = min(out.shape[1]-10, 580)
    cv2.rectangle(out,(10,10),(x2,42),(15,23,42),-1)
    cv2.rectangle(out,(10,10),(x2,42),(51,65,85),1)
    cv2.circle(out,(24,26),5,(0,255,128),-1)
    cv2.putText(out,hud,(36,30),cv2.FONT_HERSHEY_SIMPLEX,0.40,(241,245,249),1,cv2.LINE_AA)
    return out


# ─── Public class ─────────────────────────────────────────────────────────────

class VehicleDetector:
    """
    Traffic vehicle counter.  Uses YOLOv8n when available (COCO-trained),
    falls back to classical OpenCV pipeline otherwise.
    """

    def __init__(self, min_area: int = 380, conf_threshold: float = YOLO_CONF):
        self.min_area       = min_area
        self.conf_threshold = conf_threshold

    def decode_media_bytes(self, media_bytes: bytes, filename: str = "") -> Optional[np.ndarray]:
        if not media_bytes:
            return None
        if filename.lower().endswith((".mp4",".avi",".mov",".mkv")):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
                tf.write(media_bytes); tf_path = tf.name
            try:
                cap = cv2.VideoCapture(tf_path)
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total>10: cap.set(cv2.CAP_PROP_POS_FRAMES, total//4)
                ok, frm = cap.read(); cap.release()
                try: os.remove(tf_path)
                except Exception: pass
                if ok and frm is not None: return frm
            except Exception: pass
        arr = np.frombuffer(media_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def detect_vehicles(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, int, List[Dict]]:
        if img_bgr is None or img_bgr.size == 0:
            return np.zeros((100,100,3), dtype=np.uint8), 0, []
        model = _get_yolo()
        dets = []
        engine = "YOLOv8n"
        if model is not None:
            dets = self._yolo_detect(img_bgr, model)
            if len(dets) == 0:
                dets = _classical_detect(img_bgr, self.min_area)
                if len(dets) > 0:
                    engine = "Classical CV (Fallback)"
        else:
            dets   = _classical_detect(img_bgr, self.min_area)
            engine = "Classical CV"
        ann = _annotate(img_bgr, dets, engine)
        return cv2.cvtColor(ann, cv2.COLOR_BGR2RGB), len(dets), dets

    def _yolo_detect(self, img, model) -> List[Dict]:
        CLASS_NAMES = {2:"car", 3:"motorcycle", 5:"bus", 7:"truck"}
        results = model.predict(img, conf=self.conf_threshold, iou=YOLO_IOU,
                                verbose=False, classes=list(VEHICLE_CLASS_IDS))
        if not results or results[0].boxes is None:
            return []
        res    = results[0]
        boxes  = res.boxes.xyxy.cpu().numpy()
        confs  = res.boxes.conf.cpu().numpy()
        clsids = res.boxes.cls.cpu().numpy().astype(int)
        dets   = []
        for (x1,y1,x2,y2), cf, cid in zip(boxes, confs, clsids):
            if cid not in VEHICLE_CLASS_IDS: continue
            w,h = int(x2-x1), int(y2-y1)
            if w<8 or h<8: continue
            dets.append({
                "id": len(dets)+1,
                "x": int(x1), "y": int(y1), "w": w, "h": h,
                "confidence": round(float(cf),2),
                "class_name": CLASS_NAMES.get(cid,"vehicle"),
                "class_id":   int(cid),
            })
        return dets


# ─── Entry allocation ──────────────────────────────────────────────────────────

def map_detected_count_to_entries(
    detected_count: int,
    target_entry: str = "auto",
    available_entries: Optional[List[str]] = None,
) -> Dict[str, int]:
    if available_entries is None:
        available_entries = ["N1","N2","N3","S1","S2","S3","W1","W2","E1","E2"]
    alloc: Dict[str,int] = {e:0 for e in available_entries}
    if detected_count <= 0:
        return alloc
    if target_entry != "auto" and target_entry in alloc:
        alloc[target_entry] = detected_count
        return alloc
    for i in range(detected_count):
        alloc[available_entries[i % len(available_entries)]] += 1
    return alloc
