import json, re
from pathlib import Path

INTERIM = Path("data/interim")
ART = Path("artifacts"); ART.mkdir(exist_ok=True)
REPORTS = Path("reports"); REPORTS.mkdir(exist_ok=True)

# 线索正则（更强覆盖）
RX_BRACKETS = re.compile(r"《\s*([^\n》]{2,40}?)\s*》")
RX_NAME_KV  = re.compile(r"(?:产品名称|保险名称|产品简称|计划名称)[:：]\s*([^\s，。；、\n]{2,40})")
# 标题行里常见的“XX年金保险/寿险/医疗保险 … 条款|产品说明书|费率表”
RX_TITLE_PRODUCT = re.compile(
    r"([^\n]{2,40}?(?:年金保险|寿险|医疗保险|两全保险|重大疾病保险|人身保险|保险计划|保障计划))"
    r"[^\n]{0,12}?(?:保险条款|条款|产品说明书|费率表)"
)
DOC_LABEL = {"tk":"保险条款","sms":"产品说明书","flbe":"费率表"}

KEY_BOOST = ["保险","险","年金","寿险","医疗","两全","终身","增额","计划","条款","说明书","费率表"]

def score(name:str, is_heading:bool, page_no:int)->float:
    s=0.0
    L=len(name)
    if 4<=L<=30: s+=0.6
    s += 0.15*sum(1 for k in KEY_BOOST if k in name)
    if is_heading: s+=0.5
    if page_no<=2: s+=0.3
    if page_no<=6: s+=0.1
    return s

def parse_candidates(page)->list[tuple[str,float]]:
    out=[]
    page_no=page.get("page_no",0)
    text=(page.get("text") or "")
    blocks=page.get("blocks",[])

    # 1) 标题块优先：把块文本作为候选（包含“保险/条款/说明书/费率表”更加分）
    for b in blocks:
        t=(b.get("text") or "").strip()
        if not t: continue
        is_hd = bool(b.get("is_heading", False)) or len(t)<=30  # 放宽标题判定
        # 《……》与 KV
        for m in RX_BRACKETS.finditer(t):
            out.append((m.group(1).strip(), score(m.group(1).strip(), is_hd, page_no)))
        for m in RX_NAME_KV.finditer(t):
            out.append((m.group(1).strip(), score(m.group(1).strip(), is_hd, page_no)))
        # 标题行样式
        for m in RX_TITLE_PRODUCT.finditer(t):
            cand = m.group(1).strip()
            out.append((cand, score(cand, is_hd, page_no)+0.1))

        # 直接把疑似标题文本纳入候选
        if any(k in t for k in KEY_BOOST) and is_hd:
            out.append((t[:30], score(t[:30], is_hd, page_no)))

    # 2) 全页兜底
    for m in RX_BRACKETS.finditer(text):
        out.append((m.group(1).strip(), score(m.group(1).strip(), False, page_no)))
    for m in RX_NAME_KV.finditer(text):
        out.append((m.group(1).strip(), score(m.group(1).strip(), False, page_no)))
    for m in RX_TITLE_PRODUCT.finditer(text):
        cand = m.group(1).strip()
        out.append((cand, score(cand, False, page_no)))

    return out

def main():
    by_doc_candidates={}
    for doc_dir in sorted([d for d in INTERIM.iterdir() if d.is_dir()]):
        doc_id = doc_dir.name
        cands=[]
        # 扫描前6页 + 最后一页，覆盖“目录/封面/尾注”
        pages = sorted(doc_dir.glob("page_*.json"), key=lambda x:int(x.stem.split("_")[1]))
        pick = pages[:6] + (pages[-1:] if len(pages)>6 else [])
        for p in pick:
            page=json.loads(p.read_text(encoding="utf-8"))
            cands += parse_candidates(page)
        # 去噪：去掉过短/无意义候选
        clean=[]
        for n,s in cands:
            n=n.strip("《》「」[]（）() 　")
            if len(n)<2: 
                continue
            clean.append((n,s))
        clean.sort(key=lambda x:x[1], reverse=True)
        by_doc_candidates[doc_id]=clean[:15]

    # 聚合到产品编号（__ 前缀）
    base_to_docs={}
    for doc_id in by_doc_candidates:
        base = doc_id.split("__")[0]
        base_to_docs.setdefault(base, []).append(doc_id)

    product_map={}
    for base, docs in base_to_docs.items():
        pool=[]
        for d in docs:
            pool += by_doc_candidates.get(d,[])
        pool.sort(key=lambda x:x[1], reverse=True)
        # 选第一个“含 保险/险/计划 词根”的候选，否则取最高分
        best=None
        for n,s in pool:
            if any(k in n for k in ["保险","险","计划"]):
                best=n; break
        if not best and pool:
            best=pool[0][0]
        for d in docs:
            product_map[d] = best or base

    # 文档类型映射
    label_map={}
    for doc_id in product_map:
        tail = doc_id.split("__")[-1]
        label_map[doc_id] = DOC_LABEL.get(tail, "文档")

    # 输出
    (ART/"product_name_map.json").write_text(json.dumps(product_map, ensure_ascii=False, indent=2), encoding="utf-8")
    (ART/"doc_label_map.json").write_text(json.dumps(label_map, ensure_ascii=False, indent=2), encoding="utf-8")

    # 报告
    ok=sum(1 for v in product_map.values() if v and not v.isdigit())
    total=len(product_map)
    samples=[]
    for i,(d,v) in enumerate(list(product_map.items())[:30]):
        samples.append(f"- {d} → {v}（{label_map[d]}）")
    REPORTS.joinpath("product_name_map.md").write_text(
        "# Product Name Map (v2)\n"
        f"- mapped_non_numeric: {ok}/{total} = {ok/total:.2%}\n"
        + "\n".join(samples), encoding="utf-8")
    print(json.dumps({"mapped_non_numeric":ok,"total":total}, ensure_ascii=False))

if __name__ == "__main__":
    main()
