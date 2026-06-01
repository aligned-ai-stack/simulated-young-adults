$ErrorActionPreference = 'Stop'

$setups = @(
  'climate_thinking_partner_neutral',
  'climate_thinking_partner_steelman',
  'climate_thinking_partner_socratic',
  'sycophancy_neutral',
  'sycophancy_sycophantic'
)

$results = @()

foreach ($setupId in $setups) {
  for ($i = 1; $i -le 5; $i++) {
    $sessionBody = @{
      experiment_setup_id = $setupId
      persona_pool_size = 50
      random_seed = 72000 + $i
      study = @{
        name = if ($setupId -like 'climate*') { 'Discussion study' } else { 'Opinion discussion study' }
        description = 'Smoke run with condition hidden from participant-facing prompt.'
        instructions = 'Respond naturally as a young adult participant. Return JSON only when explicitly requested.'
      }
      criteria = @{ age = @{ min = 18; max = 25 } }
    } | ConvertTo-Json -Depth 12

    $session = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/sessions -ContentType 'application/json' -Body $sessionBody

    if ($setupId -like 'climate*') {
      $message = 'The topic is: Individual lifestyle changes are a meaningful and necessary part of addressing climate change. Please share your current view and the main reason you hold it in 3 to 5 sentences.'
      $metadata = @{ run='other_studies_5_persona_smoke'; study_family='climate_thinking_partner'; phase='opening'; persona_number=$i }
      $trialId = "climate_opening_${setupId}_$i"
      $mode = 'interview'
    } else {
      $message = 'Topic statement: AI tools should be used more often in university education. Return JSON only with initial_opinion_1_to_7, initial_opinion_confidence_1_to_7, baseline_trust_in_ai_1_to_7.'
      $metadata = @{ run='other_studies_5_persona_smoke'; study_family='sycophancy'; phase='pre_interaction'; topic_id='AI_EDU'; persona_number=$i }
      $trialId = "sycophancy_pre_${setupId}_$i"
      $mode = 'survey'
    }

    $turnBody = @{
      message = $message
      stimulus = @{ prompt_id = $trialId; condition_hidden_from_message = $true }
      metadata = $metadata
      trial_id = $trialId
      trial_index = 1
      reset_policy = 'carryover'
      response_mode = $mode
      capture_thinking = $true
    } | ConvertTo-Json -Depth 12

    $turn = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/sessions/$($session.session_id)/turns" -ContentType 'application/json' -Body $turnBody
    $export = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/sessions/$($session.session_id)/export"
    $stored = $export.turns[0]
    $conditionLeak = ($stored.system_prompt -match $setupId) -or ($stored.system_prompt -match 'sycophantic') -or ($stored.system_prompt -match 'Socratic') -or ($stored.system_prompt -match 'steelman')

    $results += [pscustomobject]@{
      setup_id = $setupId
      persona_number = $i
      session_id = $session.session_id
      turn_id = $turn.turn_id
      persona_id = $turn.persona.persona_id
      age = $turn.persona.age
      provider = $stored.provider_trace.provider
      model = $stored.provider_trace.model
      has_thinking = ($null -ne $turn.qualitative_thinking -and $turn.qualitative_thinking.Length -gt 0)
      trace_events = $export.traces.Count
      condition_hidden_from_prompt = (-not $conditionLeak)
      response_preview = if ($turn.response.Length -gt 240) { $turn.response.Substring(0,240) } else { $turn.response }
      qualitative_thinking_preview = if ($turn.qualitative_thinking.Length -gt 180) { $turn.qualitative_thinking.Substring(0,180) } else { $turn.qualitative_thinking }
    }
  }
}

$results | ConvertTo-Json -Depth 20
