async function fetchCurrentScenario() {
  const res = await fetch('/api/current_scenario');
  return await res.json();
}

async function postChoice(scenarioId, optionIndex) {
  const res = await fetch('/api/choose', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ scenario_id: scenarioId, option_index: optionIndex })
  });
  return await res.json();
}

function updateProgress(index, total) {
  const fill = document.getElementById('scenario-progress-fill');
  const percent = ((index) / total) * 100;
  fill.style.width = percent + '%';
}

function showScenario(data) {
  const scenarioCard = document.getElementById('scenario-card');
  const consequenceCard = document.getElementById('consequence-card');
  consequenceCard.classList.add('hidden');

  const s = data.scenario;
  updateProgress(data.index, data.total);

  document.getElementById('scenario-image').src = '/static/img/' + s.image;
  document.getElementById('scenario-title').textContent = s.title;
  document.getElementById('scenario-description').textContent = s.description;

  const optionsContainer = document.getElementById('scenario-options');
  optionsContainer.innerHTML = '';
  s.options.forEach(opt => {
    const btn = document.createElement('button');
    btn.className = 'btn-option';
    btn.textContent = opt.text;
    btn.addEventListener('click', async () => {
      await handleChoice(s.id, opt.index);
    });
    optionsContainer.appendChild(btn);
  });

  scenarioCard.classList.remove('hidden');
}

async function handleChoice(scenarioId, optionIndex) {
  const result = await postChoice(scenarioId, optionIndex);

  const scenarioCard = document.getElementById('scenario-card');
  const consequenceCard = document.getElementById('consequence-card');

  scenarioCard.classList.add('hidden');
  document.getElementById('consequence-title').textContent = result.consequence_title;
  document.getElementById('consequence-text').textContent = result.consequence_text;
  document.getElementById('consequence-image').src = '/static/img/' + result.consequence_image;

  const nextBtn = document.getElementById('consequence-next');
  if (result.next_done) {
    nextBtn.textContent = 'Top floor';
    nextBtn.onclick = () => {
      window.location.href = '/summary';
    };
  } else {
    nextBtn.textContent = 'Next floor';
    nextBtn.onclick = async () => {
      const data = await fetchCurrentScenario();
      if (data.done) {
        window.location.href = '/summary';
      } else {
        showScenario(data);
      }
    };
  }

  consequenceCard.classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', async () => {
  const data = await fetchCurrentScenario();
  if (data.done) {
    window.location.href = '/summary';
  } else {
    showScenario(data);
  }
});
