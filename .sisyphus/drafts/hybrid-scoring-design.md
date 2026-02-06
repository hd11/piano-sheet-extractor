# Hybrid Scoring 알고리즘 설계

## 개요
동일 onset에서 여러 음표 중 "가장 멜로디 같은" 음표를 선택하는 알고리즘입니다. 기존의 단순 Skyline(최고음 선택) 방식에서 벗어나, Velocity, Contour(선율의 흐름), Register(음역대)를 종합적으로 고려합니다.

## 스코어링 함수
각 노트에 대해 다음과 같이 최종 점수를 계산합니다.

$$score(note) = 0.5 \cdot velocity\_score + 0.3 \cdot contour\_score + 0.2 \cdot register\_score$$

가중치의 합은 $0.5 + 0.3 + 0.2 = 1.0$ 입니다.

### 1. velocity_score
$$velocity\_score = \frac{note.velocity}{127}$$
- **의미**: MIDI Velocity는 타건 강도를 나타냅니다.
- **근거**: 연주 시 멜로디 라인은 보통 반주보다 강하게 연주되어 강조되는 경향이 있습니다.

### 2. contour_score
$$contour\_score = \frac{1.0}{1 + |note.pitch - prev\_pitch|}$$
- **의미**: 이전 멜로디 음표와의 피치 차이(Interval)에 반비례하는 점수입니다.
- **근거**: 멜로디는 보통 도약 진행보다는 순차 진행(Stepwise motion)이나 가까운 거리의 음들로 구성되는 경향이 있습니다.

### 3. register_score
$$register\_score = \exp\left(-\frac{(note.pitch - 72)^2}{2 \cdot 12^2}\right)$$
- **의미**: 중심 피치(C5, MIDI 72)를 기준으로 하는 가우시안 분포 점수입니다 ($\sigma=12$).
- **근거**: 인간이 인지하는 멜로디는 보통 중간에서 약간 높은 음역대(C4~C6)에 집중되어 있습니다.

## 엣지 케이스 처리
- **첫 노트 (First Note)**: 이전 피치($prev\_pitch$)가 존재하지 않으므로 $contour\_score = 0.5$ (중립값)를 부여합니다.
- **동일 Onset 그룹**: $ONSET\_TOLERANCE$ (현재 0.2s) 이내의 노트들을 하나의 그룹으로 묶고, 각 노트의 $score$를 계산합니다.
- **최종 선택**: 그룹 내에서 가장 높은 $score$를 가진 노트를 선택합니다.
- **동점 처리 (Tie-breaking)**: 만약 $score$가 동일하다면, 기존 Skyline 방식과 동일하게 $pitch$가 더 높은 노트를 선택합니다.
