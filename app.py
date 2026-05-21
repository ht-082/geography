import io
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import os
import uvicorn

app = FastAPI(title="Land Area API")

# API Keys
KAKAO_KEY = "915a5f9a0d5b9b058c7509008a6cf161"
VWORLD_KEY = "A475522C-B773-3D3A-A2B3-4641C89B3EBA"

def get_pnu_from_address(address, kakao_api_key):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    params = {"query": address}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카카오 API 통신 오류: {str(e)}")
        
    if response.status_code != 200:
        if "disabled OPEN_MAP_AND_LOCAL service" in data.get('message', ''):
            raise HTTPException(status_code=400, detail="카카오 디벨로퍼스에서 [로컬] 서비스가 활성화되지 않았습니다.")
        raise HTTPException(status_code=500, detail=f"카카오 API 오류: {data.get('message', '알 수 없는 오류')}")
        
    if not data.get('documents'):
        raise HTTPException(status_code=404, detail="검색된 주소가 없습니다. 정확한 지번 주소를 입력해주세요.")
        
    doc = data['documents'][0]
    address_info = doc.get('address')
    
    if not address_info:
        raise HTTPException(status_code=404, detail="지번 주소 정보가 없습니다.")
        
    b_code = address_info.get('b_code', '')
    mountain_yn = address_info.get('mountain_yn', 'N')
    san = '2' if mountain_yn == 'Y' else '1'
    main = address_info.get('main_address_no', '').zfill(4)
    sub = address_info.get('sub_address_no', '').zfill(4)
    
    pnu = f"{b_code}{san}{main}{sub}"
    return pnu, address_info.get('address_name')


def get_land_area_vworld(pnu, vworld_key):
    url = "http://api.vworld.kr/ned/data/getLandCharacteristics"
    params = {
        'key': vworld_key,
        'domain': 'http://localhost',
        'pnu': pnu,
        'format': 'json',
        'numOfRows': '100'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"브이월드 API 통신 오류: {str(e)}")
        
    result_code = data.get('landCharacteristicss', {}).get('resultCode')
    if result_code == 'INCORRECT_KEY':
        raise HTTPException(status_code=400, detail="브이월드 API 키가 유효하지 않거나 도메인이 일치하지 않습니다.")
        
    fields = data.get('landCharacteristicss', {}).get('field', [])
    if not fields:
        raise HTTPException(status_code=404, detail="해당 필지의 토지특성정보가 데이터베이스에 존재하지 않습니다.")
        
    fields_sorted = sorted(fields, key=lambda x: x.get('stdrYear', '0'), reverse=True)
    properties = fields_sorted[0]
    
    area_str = properties.get('lndpclAr', '0')
    try:
        area_m2 = float(area_str)
    except ValueError:
        area_m2 = 0.0
        
    lndcgr = properties.get('lndcgrCodeNm', '정보 없음')
    stdr_year = properties.get('stdrYear', '알수없음')
    
    return area_m2, lndcgr, stdr_year


@app.get("/api/land-area")
def api_land_area(address: str = Query(..., description="조회할 주소")):
    pnu, std_address = get_pnu_from_address(address, KAKAO_KEY)
    area_m2, lndcgr, stdr_year = get_land_area_vworld(pnu, VWORLD_KEY)
    
    area_pyeong = area_m2 * 0.3025
    
    return {
        "standard_address": std_address,
        "pnu": pnu,
        "area_m2": round(area_m2, 2),
        "area_pyeong": round(area_pyeong, 2),
        "lndcgr": lndcgr,
        "stdr_year": stdr_year
    }

@app.get("/api/download-template")
def download_template():
    # 주소 컬럼 하나만 있는 엑셀 생성
    df = pd.DataFrame(columns=['주소'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="address_template.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.post("/api/batch-process")
async def batch_process(file: UploadFile = File(...)):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="엑셀(.xlsx) 파일만 업로드 가능합니다.")
        
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일을 읽는 중 오류가 발생했습니다: {str(e)}")
        
    if '주소' not in df.columns:
        raise HTTPException(status_code=400, detail="엑셀 파일 첫 줄(헤더)에 '주소'라는 컬럼이 있어야 합니다.")
        
    MAX_ADDRESSES = 100
    if len(df) > MAX_ADDRESSES:
        raise HTTPException(status_code=400, detail=f"기능의 안정성을 위해 한 번에 최대 {MAX_ADDRESSES}건까지만 조회할 수 있습니다. (현재 {len(df)}건)")
        
    results_pnu, results_std_addr, results_lndcgr = [], [], []
    results_area_m2, results_area_pyeong, results_year = [], [], []
    
    for address in df['주소']:
        if pd.isna(address) or str(address).strip() == '':
            results_pnu.append("공백")
            results_std_addr.append("")
            results_lndcgr.append("")
            results_area_m2.append("")
            results_area_pyeong.append("")
            results_year.append("")
            continue
            
        try:
            addr_str = str(address).strip()
            # 내부 함수 호출 (에러 시 raise 되므로 try-except로 잡음)
            pnu, std_address = get_pnu_from_address(addr_str, KAKAO_KEY)
            area_m2, lndcgr, stdr_year = get_land_area_vworld(pnu, VWORLD_KEY)
            area_pyeong = area_m2 * 0.3025
            
            results_pnu.append(pnu)
            results_std_addr.append(std_address)
            results_lndcgr.append(lndcgr)
            results_area_m2.append(round(area_m2, 2))
            results_area_pyeong.append(round(area_pyeong, 2))
            results_year.append(stdr_year)
        except HTTPException as he:
            results_pnu.append("조회 실패")
            results_std_addr.append(he.detail)
            results_lndcgr.append("-")
            results_area_m2.append("-")
            results_area_pyeong.append("-")
            results_year.append("-")
        except Exception as e:
            results_pnu.append("조회 실패")
            results_std_addr.append(str(e))
            results_lndcgr.append("-")
            results_area_m2.append("-")
            results_area_pyeong.append("-")
            results_year.append("-")
            
    df['표준주소'] = results_std_addr
    df['PNU'] = results_pnu
    df['지목'] = results_lndcgr
    df['면적(m2)'] = results_area_m2
    df['평수(평)'] = results_area_pyeong
    df['기준연도'] = results_year
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="result.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# 정적 파일 마운트 (가장 마지막에 위치해야 API 라우팅과 충돌하지 않음)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
