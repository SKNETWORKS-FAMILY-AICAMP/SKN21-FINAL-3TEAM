import { useState, useCallback, useEffect } from 'react';
import { X, Save, RotateCcw, Loader2 } from 'lucide-react';
import useGoogleStore from '../../store/googleStore';
import { toast } from '../../store/toastStore';

/**
 * 열 인덱스(0-based) → A1 표기법 열 문자 변환
 * 0→A, 1→B, ... 25→Z, 26→AA
 */
function colToLetter(col) {
  let letter = '';
  let c = col;
  while (c >= 0) {
    letter = String.fromCharCode((c % 26) + 65) + letter;
    c = Math.floor(c / 26) - 1;
  }
  return letter;
}

/**
 * (rowIdx, colIdx) → "B3" 형태의 A1 표기법
 * rowIdx, colIdx 모두 0-based (데이터 행 기준, 헤더 제외)
 */
function toA1(rowIdx, colIdx) {
  return `${colToLetter(colIdx)}${rowIdx + 1}`;
}

/**
 * 셀 값 기반 색상 스타일 반환 (실제 Google Sheets 스타일 모방)
 */
function getCellStyle(value, rowIdx, colIdx, activeTab, allValues) {
  if (!value) return {};
  const v = String(value).trim();

  // Gantt 바 (■ 문자)
  if (v === '■') return { backgroundColor: '#4a86e8', color: '#4a86e8' };

  // 상태 값 컬러링
  const statusColors = {
    'Done': { backgroundColor: '#d9ead3', color: '#274e13' },
    'In Progress': { backgroundColor: '#c9daf8', color: '#1c4587' },
    'Review': { backgroundColor: '#fce5cd', color: '#7f6000' },
    'To Do': { backgroundColor: '#efefef', color: '#666666' },
  };
  if (statusColors[v]) return statusColors[v];

  // 우선순위 컬러링
  const priorityColors = {
    'HIGH': { backgroundColor: '#f4cccc', color: '#990000' },
    'MEDIUM': { backgroundColor: '#fff2cc', color: '#7f6000' },
    'LOW': { backgroundColor: '#d9ead3', color: '#274e13' },
  };
  if (priorityColors[v]) return priorityColors[v];

  // 위험도 컬러링 (Risk Analysis 탭)
  if (activeTab === 'Risk Analysis') {
    const riskColors = {
      '높음': { backgroundColor: '#ea4335', color: '#ffffff' },
      '중간': { backgroundColor: '#fbbc04', color: '#333333' },
      '낮음': { backgroundColor: '#34a853', color: '#ffffff' },
    };
    if (riskColors[v]) return riskColors[v];
  }

  // D-day 컬러링 (마감 초과 = 빨간, D-Day = 주황, 남은일수 = 기본)
  if (v.includes('일 초과')) return { backgroundColor: '#f4cccc', color: '#990000' };
  if (v === 'D-Day') return { backgroundColor: '#fce5cd', color: '#7f6000' };

  // 섹션 헤더 (Dashboard / Weekly Report 탭)
  if (colIdx === 0) {
    const sectionStyles = {
      '프로젝트 통합 대시보드': { backgroundColor: '#1a237e', color: '#ffffff', fontWeight: 'bold', fontSize: '13px' },
      '주간 보고서': { backgroundColor: '#1a237e', color: '#ffffff', fontWeight: 'bold', fontSize: '13px' },
      '프로젝트 리스크 분석': { backgroundColor: '#b71c1c', color: '#ffffff', fontWeight: 'bold', fontSize: '13px' },
      '── 파이프라인 태스크 ──': { backgroundColor: '#e8e8e8', fontWeight: 'bold' },
      '── 마감 초과 태스크 ──': { backgroundColor: '#e8e8e8', fontWeight: 'bold' },
      '── 일정 현황 ──': { backgroundColor: '#e8e8e8', fontWeight: 'bold' },
      '── 결재 현황 ──': { backgroundColor: '#e8e8e8', fontWeight: 'bold' },
      '── 완료 ──': { backgroundColor: '#d9ead3', fontWeight: 'bold' },
      '── 진행 중 ──': { backgroundColor: '#c9daf8', fontWeight: 'bold' },
      '── 다음 주 예정 ──': { backgroundColor: '#fff2cc', fontWeight: 'bold' },
      '── 회의 일정 ──': { backgroundColor: '#e8d5f5', fontWeight: 'bold' },
      '── 블로커/이슈 ──': { backgroundColor: '#f4cccc', fontWeight: 'bold' },
    };
    if (sectionStyles[v]) return sectionStyles[v];
  }

  // 진행률 퍼센트 바 (█ 문자)
  if (v.includes('█')) return { backgroundColor: '#c9daf8', color: '#1c4587', fontFamily: 'monospace' };

  // WBS 레벨별 색상
  if (activeTab === 'WBS' && colIdx === 1) {
    if (v === '1') return { backgroundColor: '#3874cb', color: '#ffffff', fontWeight: 'bold' };
    if (v === '2') return { backgroundColor: '#aed1f5', color: '#000000' };
  }

  // 테이블 서브 헤더 감지 (Dashboard/Report 탭의 컬럼 헤더 행)
  const subHeaders = new Set(['상태', '건수', '담당자', '우선순위', '태스크명', '마감일', '초과일수', '유형',
    '태스크', '진행 상황', '회의명', '날짜', '비고', '결재명', '위험도', '카테고리', '설명', '관련 태스크', '권장 조치',
    'WBS Code', 'Level', '이름', '항목', '바', '비율']);
  if (colIdx === 0 && subHeaders.has(v) && rowIdx > 0) {
    return { backgroundColor: '#f3f3f3', fontWeight: 'bold' };
  }

  return {};
}

export default function SheetPreview({ spreadsheetId, onClose }) {
  const {
    sheetPreview,
    sheetPreviewLoading,
    sheetPreviewError,
    fetchSheetPreview,
    updateSheetData,
    clearSheetPreview,
  } = useGoogleStore();

  const [activeTab, setActiveTab] = useState(null);
  const [editedCells, setEditedCells] = useState(new Map());
  const [editingCell, setEditingCell] = useState(null); // { row, col }
  const [saving, setSaving] = useState(false);

  // 탭 로드
  const loadTab = useCallback(async (tabName) => {
    setActiveTab(tabName);
    setEditedCells(new Map());
    setEditingCell(null);
    try {
      await fetchSheetPreview(spreadsheetId, tabName);
    } catch {
      // error handled in store
    }
  }, [spreadsheetId, fetchSheetPreview]);

  // 첫 로드 — 백엔드가 실제 탭 이름을 자동 감지하므로 기본값으로 요청
  useEffect(() => {
    loadTab('project');
  }, [spreadsheetId]); // eslint-disable-line react-hooks/exhaustive-deps

  const values = sheetPreview?.values || [];
  const tabs = sheetPreview?.tabs || [];
  
  const maxCols = values.reduce((max, row) => Math.max(max, row.length), 0);
  const cols = Array.from({ length: maxCols }, (_, i) => i);

  // 셀 클릭 → 편집 모드
  const handleCellClick = (rowIdx, colIdx) => {
    setEditingCell({ row: rowIdx, col: colIdx });
  };

  // 셀 값 변경
  const handleCellChange = (rowIdx, colIdx, newValue) => {
    const key = `${rowIdx}:${colIdx}`;
    const originalValue = values[rowIdx]?.[colIdx] || '';
    const updated = new Map(editedCells);

    if (newValue === originalValue) {
      updated.delete(key);
    } else {
      updated.set(key, { rowIdx, colIdx, value: newValue });
    }
    setEditedCells(updated);
  };

  // 편집 완료 (blur / Enter)
  const handleCellBlur = () => {
    setEditingCell(null);
  };

  // 셀 표시 값 (편집된 값 우선)
  const getCellValue = (rowIdx, colIdx) => {
    const key = `${rowIdx}:${colIdx}`;
    if (editedCells.has(key)) {
      return editedCells.get(key).value;
    }
    return values[rowIdx]?.[colIdx] || '';
  };

  // 저장
  const handleSave = async () => {
    if (editedCells.size === 0) return;
    setSaving(true);
    try {
      const updates = [];
      for (const [, edit] of editedCells) {
        const cell = toA1(edit.rowIdx, edit.colIdx);
        updates.push({ cell, value: edit.value });
      }
      await updateSheetData(spreadsheetId, activeTab || 'project', updates);
      toast.success(`${updates.length}개 셀이 저장되었습니다.`);
      setEditedCells(new Map());
      setEditingCell(null);
      // 새로고침
      await fetchSheetPreview(spreadsheetId, activeTab || 'project');
    } catch {
      toast.error('저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  // 취소
  const handleCancel = () => {
    setEditedCells(new Map());
    setEditingCell(null);
  };

  // 닫기
  const handleClose = () => {
    clearSheetPreview();
    setEditedCells(new Map());
    setEditingCell(null);
    onClose?.();
  };

  return (
    <div className="mt-2 border border-neutral-divider rounded-lg overflow-hidden bg-surface-base">
      {/* 상단 바: 탭 + 버튼 */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-hover border-b border-neutral-divider">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => loadTab(tab)}
              className={`text-xs px-3 py-1.5 rounded font-semibold transition border ${
                (activeTab || 'project') === tab
                  ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400 border-primary-300 dark:border-primary-700 shadow-sm'
                  : 'border-transparent text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          {editedCells.size > 0 && (
            <>
              <button
                onClick={handleCancel}
                className="text-xs px-2.5 py-1.5 rounded border border-neutral-divider text-neutral-muted hover:bg-surface-base transition flex items-center gap-1"
              >
                <RotateCcw size={12} />
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-xs px-2.5 py-1.5 rounded bg-primary-600 text-white hover:bg-primary-700 transition flex items-center gap-1 disabled:opacity-50"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                저장 ({editedCells.size})
              </button>
            </>
          )}
          <button
            onClick={handleClose}
            className="p-1 rounded hover:bg-surface-base text-neutral-muted transition"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* 로딩 */}
      {sheetPreviewLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-primary-600" />
          <span className="ml-2 text-sm text-neutral-muted">데이터 로딩 중...</span>
        </div>
      )}

      {/* 에러 */}
      {sheetPreviewError && (
        <div className="px-3 py-4 text-center">
          <p className="text-sm text-error">{sheetPreviewError}</p>
        </div>
      )}

      {/* 테이블 */}
      {!sheetPreviewLoading && !sheetPreviewError && values.length > 0 && (
        <div className="overflow-auto max-h-[400px]">
          <table className="w-full text-xs border-collapse font-sans">
            <thead className="sticky top-0 z-20 shadow-sm">
              <tr>
                <th className="w-10 min-w-[40px] bg-neutral-100 dark:bg-neutral-800 border-b border-r border-neutral-divider sticky left-0 z-30"></th>
                {cols.map((colIdx) => (
                  <th
                    key={`col-${colIdx}`}
                    className="px-2.5 py-1 text-center font-medium text-neutral-500 bg-neutral-100 dark:bg-neutral-800 border-b border-r border-neutral-divider"
                  >
                    {colToLetter(colIdx)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {values.map((row, rowIdx) => {
                // 행 전체에 적용할 섹션 스타일 감지
                const firstCell = String(row[0] || '').trim();
                const sectionRowStyle = getCellStyle(firstCell, rowIdx, 0, activeTab, values);
                const isSectionRow = sectionRowStyle.fontWeight === 'bold' || (sectionRowStyle.fontSize && sectionRowStyle.fontSize !== undefined);

                return (
                <tr key={rowIdx} className={`transition-colors ${!isSectionRow ? 'hover:bg-surface-hover' : ''}`}>
                  <td className="w-10 min-w-[40px] text-center font-medium text-neutral-500 bg-neutral-100 dark:bg-neutral-800 border-b border-r border-neutral-divider sticky left-0 z-10 select-none">
                    {rowIdx + 1}
                  </td>
                  {cols.map((colIdx) => {
                    const isEditing = editingCell?.row === rowIdx && editingCell?.col === colIdx;
                    const isEdited = editedCells.has(`${rowIdx}:${colIdx}`);
                    const cellValue = getCellValue(rowIdx, colIdx);
                    const ownStyle = getCellStyle(cellValue, rowIdx, colIdx, activeTab, values);
                    const hasCellStyle = Object.keys(ownStyle).length > 0;
                    // 섹션 행이면 전체 행에 배경 적용
                    const cellStyle = hasCellStyle ? ownStyle : (isSectionRow ? sectionRowStyle : {});
                    const hasAnyStyle = Object.keys(cellStyle).length > 0;
                    const isHeader = rowIdx === 0 && activeTab !== 'Dashboard' && activeTab !== 'Risk Analysis' && activeTab !== 'Weekly Report';

                    return (
                      <td
                        key={colIdx}
                        onClick={() => handleCellClick(rowIdx, colIdx)}
                        style={!isEdited && hasAnyStyle ? cellStyle : undefined}
                        className={`px-2.5 py-1.5 border-b border-r border-neutral-divider cursor-pointer transition-colors max-w-[200px] truncate ${
                          isEdited ? 'bg-amber-50 dark:bg-amber-900/20' : hasAnyStyle ? '' : 'bg-white dark:bg-neutral-900'
                        } ${isHeader ? 'font-semibold bg-neutral-50 dark:bg-neutral-800/50' : ''}`}
                      >
                        {isEditing ? (
                          <input
                            type="text"
                            defaultValue={cellValue}
                            autoFocus
                            onBlur={(e) => {
                              handleCellChange(rowIdx, colIdx, e.target.value);
                              handleCellBlur();
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleCellChange(rowIdx, colIdx, e.target.value);
                                handleCellBlur();
                              }
                              if (e.key === 'Escape') {
                                handleCellBlur();
                              }
                            }}
                            className="w-full px-1 py-0.5 text-xs border border-primary-400 rounded outline-none bg-white dark:bg-neutral-900"
                          />
                        ) : (
                          <span className="whitespace-nowrap" style={hasCellStyle ? { color: 'inherit' } : undefined}>
                            {cellValue}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 빈 데이터 */}
      {!sheetPreviewLoading && !sheetPreviewError && values.length === 0 && (
        <div className="px-3 py-6 text-center">
          <p className="text-sm text-neutral-muted">데이터가 없습니다</p>
        </div>
      )}
    </div>
  );
}
