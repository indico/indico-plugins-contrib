# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from io import BytesIO

import pytest

from indico.core import signals
from indico.modules.designer import TemplateType
from indico.modules.designer.models.images import DesignerImageFile
from indico.modules.designer.testing.fixtures import DUMMY_BMP_IMAGE
from indico.modules.designer.util import get_inherited_templates


@pytest.fixture
def create_image(db):
    def _create(template, filename):
        image = DesignerImageFile(filename=filename, content_type='image/bmp', template=template)
        image.save(BytesIO(DUMMY_BMP_IMAGE))
        db.session.flush()
        return image

    return _create


@pytest.fixture
def category_designer_template(dummy_category, create_dummy_designer_template):
    return create_dummy_designer_template('Conference poster', category=dummy_category, type=TemplateType.poster)


@pytest.mark.usefixtures('event_manager')
def test_designer_template_details(dummy_event, dummy_designer_template, token_headers, test_client):
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/designer-templates/{dummy_designer_template.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_designer_template.id,
        'title': 'Default ticket',
        'data': dummy_designer_template.data,
        'background_url': None,
        'images': [],
    }


@pytest.mark.usefixtures('event_manager')
def test_designer_template_serves_its_images(
    dummy_event, dummy_designer_template, create_image, token_headers, test_client
):
    second = create_image(dummy_designer_template, 'b.bmp')
    first = create_image(dummy_designer_template, 'a.bmp')
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/designer-templates/{dummy_designer_template.id}', headers=token_headers
    )
    assert resp.status_code == 200
    assert [image['id'] for image in resp.json['images']] == sorted([first.id, second.id])
    assert resp.json['images'][0]['download_url'] == min([first, second], key=lambda image: image.id).download_url


@pytest.mark.usefixtures('event_manager')
def test_designer_template_serves_its_background(
    db, dummy_event, dummy_designer_template, create_image, token_headers, test_client
):
    background = create_image(dummy_designer_template, 'background.bmp')
    dummy_designer_template.background_image = background
    db.session.flush()
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/designer-templates/{dummy_designer_template.id}', headers=token_headers
    )
    assert resp.json['background_url'] == background.download_url
    assert not resp.json['background_url'].startswith('http')


@pytest.mark.usefixtures('event_manager')
def test_designer_template_list_includes_inherited_templates(
    dummy_event, dummy_designer_template, category_designer_template, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/designer-templates', headers=token_headers)
    assert resp.status_code == 200
    expected = get_inherited_templates(dummy_event) | set(dummy_event.designer_templates)
    results = resp.json['results']
    assert [tpl['id'] for tpl in results] == [tpl.id for tpl in sorted(expected, key=lambda t: (t.title.lower(), t.id))]
    assert {category_designer_template.id, dummy_designer_template.id} <= {tpl['id'] for tpl in results}
    assert resp.json['count'] == len(expected)
    assert resp.json['next_offset'] is None


@pytest.mark.usefixtures('event_manager')
def test_designer_template_list_honours_the_filter_signal(
    dummy_event, dummy_designer_template, category_designer_template, token_headers, test_client
):
    def _drop_inherited(sender, badge_templates, **kwargs):
        badge_templates[:] = [tpl for tpl in badge_templates if tpl.id != category_designer_template.id]

    with signals.event.filter_selectable_badges.connected_to(_drop_inherited):
        resp = test_client.get(f'/api/v1/events/{dummy_event.id}/designer-templates', headers=token_headers)
    assert category_designer_template.id not in {tpl['id'] for tpl in resp.json['results']}
    assert dummy_designer_template.id in {tpl['id'] for tpl in resp.json['results']}


def test_designer_templates_are_manager_only(dummy_event, dummy_designer_template, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/designer-templates', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(
        f'/api/v1/events/{dummy_event.id}/designer-templates/{dummy_designer_template.id}', headers=outsider_headers
    )
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_template_of_an_unrelated_event_is_not_found(
    dummy_event, create_event, create_dummy_designer_template, token_headers, test_client
):
    other = create_dummy_designer_template('Elsewhere', event=create_event())
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/designer-templates/{other.id}', headers=token_headers)
    assert resp.status_code == 404


def as_image_map(images):
    return {str(image['id']): image['download_url'] for image in images} or None


@pytest.mark.usefixtures('event_manager')
def test_designer_template_matches_current_api(
    dummy_event, dummy_designer_template, create_image, db, token_headers, test_client, indico_api, same_json
):
    background = create_image(dummy_designer_template, 'background.bmp')
    dummy_designer_template.background_image = background
    create_image(dummy_designer_template, 'logo.bmp')
    db.session.flush()
    current = indico_api(f'/event/{dummy_event.id}/manage/designer/{dummy_designer_template.id}/data')
    theirs = current['template'] | {'backside_template_id': current['backside_template_id']}
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/designer-templates/{dummy_designer_template.id}', headers=token_headers
    ).json
    same_json(
        new,
        theirs,
        same=('title', 'data', 'background_url'),
        renamed={'id': ('backside_template_id', None), 'images': ('images', as_image_map)},
    )


@pytest.mark.usefixtures('event_manager')
def test_designer_template_without_images_matches_current_api(
    dummy_event, dummy_designer_template, token_headers, test_client, indico_api, same_json
):
    current = indico_api(f'/event/{dummy_event.id}/manage/designer/{dummy_designer_template.id}/data')
    theirs = current['template'] | {'backside_template_id': current['backside_template_id']}
    new = test_client.get(
        f'/api/v1/events/{dummy_event.id}/designer-templates/{dummy_designer_template.id}', headers=token_headers
    ).json
    same_json(
        new,
        theirs,
        same=('title', 'data', 'background_url'),
        renamed={'id': ('backside_template_id', None), 'images': ('images', as_image_map)},
    )
