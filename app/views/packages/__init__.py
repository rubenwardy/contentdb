# Content DB
# Copyright (C) 2018  rubenwardy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from flask import *
from flask_user import *
from flask.ext import menu
from app import app
from app.models import *
from app.tasks.importtasks import importRepoScreenshot, makeVCSRelease

from app.utils import *

from celery import uuid
from flask_wtf import FlaskForm
from wtforms import *
from wtforms.validators import *
from wtforms.ext.sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField

# TODO: the following could be made into one route, except I"m not sure how
# to do the menu

@menu.register_menu(app, ".mods", "Mods", order=11, endpoint_arguments_constructor=lambda: { 'type': 'mod' })
@menu.register_menu(app, ".games", "Games", order=12, endpoint_arguments_constructor=lambda: { 'type': 'game' })
@menu.register_menu(app, ".txp", "Texture Packs", order=13, endpoint_arguments_constructor=lambda: { 'type': 'txp' })
@app.route("/packages/")
def packages_page():
	type = request.args.get("type")
	if type is not None:
		type = PackageType[type.upper()]

	title = "Packages"
	query = Package.query.filter_by(soft_deleted=False)

	if type is not None:
		title = type.value + "s"
		query = query.filter_by(type=type, approved=True)

	search = request.args.get("q")
	if search is not None:
		query = query.filter(Package.title.contains(search))

	if shouldReturnJson():
		pkgs = [package.getAsDictionary(app.config["BASE_URL"]) \
				for package in query.all() if package.getDownloadRelease() is not None]
		return jsonify(pkgs)
	else:
		tags = Tag.query.all()
		return render_template("packages/list.html", title=title, packages=query.all(), \
				query=search, tags=tags, type=None if type is None else type.toName())


def getReleases(package):
	if package.checkPerm(current_user, Permission.MAKE_RELEASE):
		return package.releases
	else:
		return [rel for rel in package.releases if rel.approved]


@app.route("/packages/<author>/<name>/")
@is_package_page
def package_page(package):
	if shouldReturnJson():
		return jsonify(package.getAsDictionary(app.config["BASE_URL"]))
	else:
		clearNotifications(package.getDetailsURL())

		releases = getReleases(package)
		requests = [r for r in package.requests if r.status == 0]
		return render_template("packages/view.html", package=package, releases=releases, requests=requests)


@app.route("/packages/<author>/<name>/download/")
@is_package_page
def package_download_page(package):
	release = package.getDownloadRelease()

	if release is None:
		if "application/zip" in request.accept_mimetypes and \
				not "text/html" in request.accept_mimetypes:
			return "", 204
		else:
			flash("No download available.", "error")
			return redirect(package.getDetailsURL())
	else:
		return redirect(release.url, code=302)


class PackageForm(FlaskForm):
	name          = StringField("Name", [InputRequired(), Length(1, 20), Regexp("^[a-z0-9_]", 0, "Lower case letters (a-z), digits (0-9), and underscores (_) only")])
	title         = StringField("Title", [InputRequired(), Length(3, 50)])
	shortDesc     = StringField("Short Description (Plaintext)", [InputRequired(), Length(1,200)])
	desc          = TextAreaField("Long Description (Markdown)", [Optional(), Length(0,10000)])
	type          = SelectField("Type", [InputRequired()], choices=PackageType.choices(), coerce=PackageType.coerce, default=PackageType.MOD)
	license       = QuerySelectField("License", [InputRequired()], query_factory=lambda: License.query, get_pk=lambda a: a.id, get_label=lambda a: a.name)
	provides_str  = StringField("Provides (mods included in package)", [Optional(), Length(0,1000)])
	tags          = QuerySelectMultipleField('Tags', query_factory=lambda: Tag.query.order_by(db.asc(Tag.name)), get_pk=lambda a: a.id, get_label=lambda a: a.title)
	harddep_str   = StringField("Hard Dependencies", [Optional(), Length(0,1000)])
	softdep_str   = StringField("Soft Dependencies", [Optional(), Length(0,1000)])
	repo          = StringField("Repo URL", [Optional(), URL()])
	website       = StringField("Website URL", [Optional(), URL()])
	issueTracker  = StringField("Issue Tracker URL", [Optional(), URL()])
	forums	      = IntegerField("Forum Topic ID", [Optional(), NumberRange(0,999999)])
	submit	      = SubmitField("Save")

@app.route("/packages/new/", methods=["GET", "POST"])
@app.route("/packages/<author>/<name>/edit/", methods=["GET", "POST"])
@login_required
def create_edit_package_page(author=None, name=None):
	package = None
	form = None
	if author is None:
		form = PackageForm(formdata=request.form)
		author = request.args.get("author")
		if author is None or author == current_user.username:
			author = current_user
		else:
			author = User.query.filter_by(username=author).first()
			if author is None:
				flash("Unable to find that user", "error")
				return redirect(url_for("create_edit_package_page"))

			if not author.checkPerm(current_user, Permission.CHANGE_AUTHOR):
				flash("Permission denied", "error")
				return redirect(url_for("create_edit_package_page"))

	else:
		package = getPackageByInfo(author, name)
		if not package.checkPerm(current_user, Permission.EDIT_PACKAGE):
			return redirect(package.getDetailsURL())

		author = package.author

		form = PackageForm(formdata=request.form, obj=package)

	# Initial form class from post data and default data
	if request.method == "GET" and package is not None:
		deps = package.dependencies
		form.harddep_str.data  = ",".join([str(x) for x in deps if not x.optional])
		form.softdep_str.data  = ",".join([str(x) for x in deps if     x.optional])
		form.provides_str.data = MetaPackage.ListToSpec(package.provides)

	if request.method == "POST" and form.validate():
		wasNew = False
		if not package:
			package = Package.query.filter_by(name=form["name"].data, author_id=author.id).first()
			if package is not None:
				if package.soft_deleted:
					Package.query.filter_by(name=form["name"].data, author_id=author.id).delete()
				else:
					flash("Package already exists!", "error")
					return redirect(url_for("create_edit_package_page"))

			package = Package()
			package.author = author
			wasNew = True
		else:
			triggerNotif(package.author, current_user,
					"{} edited".format(package.title), package.getDetailsURL())

		form.populate_obj(package) # copy to row

		mpackage_cache = {}
		package.provides.clear()
		mpackages = MetaPackage.SpecToList(form.provides_str.data, mpackage_cache)
		for m in mpackages:
			package.provides.append(m)

		Dependency.query.filter_by(depender=package).delete()
		deps = Dependency.SpecToList(package, form.harddep_str.data, mpackage_cache)
		for dep in deps:
			dep.optional = False
			db.session.add(dep)

		deps = Dependency.SpecToList(package, form.softdep_str.data, mpackage_cache)
		for dep in deps:
			dep.optional = True
			db.session.add(dep)

		if wasNew and package.type == PackageType.MOD and not package.name in mpackage_cache:
			m = MetaPackage.GetOrCreate(package.name, mpackage_cache)
			package.provides.append(m)

		package.tags.clear()
		for tag in form.tags.raw_data:
			package.tags.append(Tag.query.get(tag))

		db.session.commit() # save

		if wasNew and package.canImportScreenshot():
			task = importRepoScreenshot.delay(package.id)
			return redirect(url_for("check_task", id=task.id, r=package.getDetailsURL()))

		return redirect(package.getDetailsURL())

	package_query = Package.query.filter_by(approved=True, soft_deleted=False)
	if package is not None:
		package_query = package_query.filter(Package.id != package.id)

	enableWizard = name is None and request.method != "POST"
	return render_template("packages/create_edit.html", package=package, \
			form=form, author=author, enable_wizard=enableWizard, \
			packages=package_query.all(), \
			mpackages=MetaPackage.query.order_by(db.asc(MetaPackage.name)).all())

@app.route("/packages/<author>/<name>/approve/", methods=["POST"])
@login_required
@is_package_page
def approve_package_page(package):
	if not package.checkPerm(current_user, Permission.APPROVE_NEW):
		flash("You don't have permission to do that.", "error")

	elif package.approved:
		flash("Package has already been approved", "error")

	else:
		package.approved = True

		screenshots = PackageScreenshot.query.filter_by(package=package, approved=False).all()
		for s in screenshots:
			s.approved = True

		triggerNotif(package.author, current_user,
				"{} approved".format(package.title), package.getDetailsURL())
		db.session.commit()

	return redirect(package.getDetailsURL())


@app.route("/packages/<author>/<name>/delete/", methods=["GET", "POST"])
@login_required
@is_package_page
def delete_package_page(package):
	if request.method == "GET":
		return render_template("packages/delete.html", package=package)

	if not package.checkPerm(current_user, Permission.DELETE_PACKAGE):
		flash("You don't have permission to do that.", "error")

	package.soft_deleted = True

	url = url_for("user_profile_page", username=package.author.username)
	triggerNotif(package.author, current_user,
			"{} deleted".format(package.title), url)
	db.session.commit()

	flash("Deleted package", "success")

	return redirect(url)

from . import todo, screenshots, editrequests, releases