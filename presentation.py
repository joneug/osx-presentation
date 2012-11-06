#!/usr/bin/env python2.6
# -*- coding: utf-8 -*-


"""
A PDF presentation tool for Mac OS X

Copyright (c) 2011, IIHM/LIG - Renaud Blanch <http://iihm.imag.fr/blanch/>
Licence: GPLv3 or higher <http://www.gnu.org/licenses/gpl.html>
"""


# imports ####################################################################

import sys
import os
import time

from collections import defaultdict

from objc import *
from Foundation import *
from Cocoa import *
from Quartz import *
from WebKit import *


# constants ##################################################################

PRESENTER_FRAME = ((100., 100.), (800., 600.))
def nop(): pass


# handling args ##############################################################

name, args = sys.argv[0], sys.argv[1:]
assert len(args) == 1, "usage"

path = args[0]


# application init ###########################################################

pool = NSAutoreleasePool.alloc().init()
app = NSApplication.sharedApplication()
app.activateIgnoringOtherApps_(True)


# opening presentation #######################################################

url = NSURL.fileURLWithPath_(path)
pdf = PDFDocument.alloc().initWithURL_(url)

page_count = pdf.pageCount()

notes = defaultdict(list)
for page_number in range(page_count):
	page = pdf.pageAtIndex_(page_number)
	page.setDisplaysAnnotations_(False)
	for annotation in page.annotations():
		if type(annotation) == PDFAnnotationText:
			notes[page_number].append(annotation.contents())


# page navigation ############################################################

past_pages = []
current_page = 0
future_pages = []

def _goto(page):
	global current_page
	current_page = page
	toggle_web_view(visible=False)
	redisplayer.display_()


def goto_page(page):
	page = min(max(0, page), page_count-1)
	if page == current_page:
		return
	del future_pages[:]
	past_pages.append(current_page)
	_goto(page)


def _push_pop_page(pop_pages, push_pages):
	def action():
		try:
			page = pop_pages.pop()
		except IndexError:
			return
		push_pages.append(current_page)
		_goto(page)
	return action

back    = _push_pop_page(past_pages, future_pages)
forward = _push_pop_page(future_pages, past_pages)


def next_page():
	goto_page(current_page+1)

def prev_page():
	goto_page(current_page-1)

def home_page():
	goto_page(0)

def last_page():
	goto_page(page_count-1)


# handling redisplay #########################################################

class Redisplayer(NSObject):
	def display_(self, timer=None):
		for window in app.windows():
			window.display()
redisplayer = Redisplayer.alloc().init()


# handling full screens ######################################################

fullscreen = False
def toggle_fullscreen():
	global fullscreen
	for window, screen in reversed(zip(app.windows(), NSScreen.screens())):
		view = window.contentView()
		if fullscreen:
			view.exitFullScreenModeWithOptions_({})
		else:
			view.enterFullScreenMode_withOptions_(screen, {}) 
		window.makeFirstResponder_(view)
	fullscreen = not fullscreen


# presenter view #############################################################

class PresenterView(NSView):
	def drawRect_(self, rect):
		bounds = self.bounds()
		width, height = bounds.size

		margin = width / 20
		current_width = width / 2
		font_size = margin / 3
	
		NSRectFillUsingOperation(bounds, NSCompositeClear)

		# current 
		self.page = pdf.pageAtIndex_(current_page)
		page_rect = self.page.boundsForBox_(kPDFDisplayBoxCropBox)
		_, (w, h) = page_rect
		r = current_width/w
	
		self.transform = NSAffineTransform.transform()
		self.transform.translateXBy_yBy_(margin, height/2.)
		self.transform.scaleXBy_yBy_(r, r)
		self.transform.translateXBy_yBy_(0., -h/2.)
		self.transform.concat()
		
		NSEraseRect(page_rect)
		self.page.drawWithBox_(kPDFDisplayBoxCropBox)
		
		# links
		NSColor.blueColor().setFill()
		for annotation in self.page.annotations():
			annotation_type = type(annotation)
			if annotation_type == PDFAnnotationLink:
				NSFrameRectWithWidth(annotation.bounds(), .5)
		self.resetCursorRects()

		self.transform.invert()
		self.transform.concat()
		

		# time
		now = NSString.stringWithString_(time.strftime("%H:%M:%S"))
		now.drawAtPoint_withAttributes_((margin, height-margin*2), {
			NSFontAttributeName:            NSFont.labelFontOfSize_(margin),
			NSForegroundColorAttributeName: NSColor.whiteColor(),
		})
	
		# page number
		page_number = NSString.stringWithString_("%s (%s/%s)" % (
			self.page.label(), current_page+1, page_count))
		attr = {
			NSFontAttributeName:            NSFont.labelFontOfSize_(font_size),
			NSForegroundColorAttributeName: NSColor.whiteColor(),
		}
		tw, _ = page_number.sizeWithAttributes_(attr)
		page_number.drawAtPoint_withAttributes_((margin+current_width-tw,
		                                         height-margin*2.), attr)

		# notes
		note = NSString.stringWithString_("\n".join(notes[current_page]))
		note.drawAtPoint_withAttributes_((margin, margin), {
			NSFontAttributeName:            NSFont.labelFontOfSize_(font_size),
			NSForegroundColorAttributeName: NSColor.whiteColor(),
		})
		
		# next page
		try:
			page = pdf.pageAtIndex_(current_page+1)
		except:
			return
		page_rect = page.boundsForBox_(kPDFDisplayBoxCropBox)
		_, (w, h) = page_rect
		r = (width - (3*margin + current_width))/w
	
		transform = NSAffineTransform.transform()
		transform.translateXBy_yBy_(2*margin+current_width, height/2.)
		transform.scaleXBy_yBy_(r, r)
		transform.translateXBy_yBy_(0., -h/2.)
		transform.concat()

		NSEraseRect(page_rect)
		page.drawWithBox_(kPDFDisplayBoxCropBox)
		transform.invert()
		transform.concat()
		
	
	def resetCursorRects(self):
		self.discardCursorRects()
		for annotation in self.page.annotations():
			annotation_type = type(annotation)
			if annotation_type == PDFAnnotationLink:
				origin, size = annotation.bounds()
				rect = (self.transform.transformPoint_(origin),
				        self.transform.transformSize_(size))
				self.addCursorRect_cursor_(rect, NSCursor.pointingHandCursor())
	
	
	def keyDown_(self, event):
		c = event.characters()
		if c == "q":
			app.terminate_(self)
		
		action = {
			"f":                     toggle_fullscreen,
			"w":                     toggle_web_view,
			NSUpArrowFunctionKey:    prev_page,
			NSLeftArrowFunctionKey:  prev_page,
			NSDownArrowFunctionKey:  next_page,
			NSRightArrowFunctionKey: next_page,
			NSHomeFunctionKey:       home_page,
			NSEndFunctionKey:        last_page,
			NSPageUpFunctionKey:     back,
			NSPageDownFunctionKey:   forward,
		}.get(c, nop)
		action()
		
	
	def mouseUp_(self, event):
		point = self.transform.transformPoint_(event.locationInWindow())
		annotation = self.page.annotationAtPoint_(point)
		if annotation is None:
			return

		if type(annotation) != PDFAnnotationLink:
			return

		action = annotation.mouseUpAction()

		if type(action) == PDFActionNamed:
			action_name = action.name()
			action = {
				kPDFActionNamedNextPage:     next_page,
				kPDFActionNamedPreviousPage: prev_page,
				kPDFActionNamedFirstPage:    home_page,
				kPDFActionNamedLastPage:     last_page,
				kPDFActionNamedGoBack:       back,
				kPDFActionNamedGoForward:    forward,
#				kPDFActionNamedGoToPage = 7,
#				kPDFActionNamedFind = 8,
#				kPDFActionNamedPrint = 9,
			}.get(action_name, nop)
			action()
			return

		destination = annotation.destination()
		if destination:
			goto_page(pdf.indexForPage_(destination.page()))
			return
		
		url = annotation.URL()
		if url:
			web_view.mainFrame().loadRequest_(NSURLRequest.requestWithURL_(url))
			toggle_web_view(visible=True)


# presentation ###############################################################

class SlideView(NSView):
	def drawRect_(self, rect):
		bounds = self.bounds()
		width, height = bounds.size
		
		NSRectFillUsingOperation(bounds, NSCompositeClear)
	
		# current page
		page = pdf.pageAtIndex_(current_page)
		page_rect = page.boundsForBox_(kPDFDisplayBoxCropBox)
		_, (w, h) = page_rect
		r = min(width/w, height/h)
	
		transform = NSAffineTransform.transform()
		transform.translateXBy_yBy_(width/2., height/2.)
		transform.scaleXBy_yBy_(r, r)
		transform.translateXBy_yBy_(-w/2., -h/2.)
		transform.concat()

		NSEraseRect(page_rect)
		page.drawWithBox_(kPDFDisplayBoxCropBox)
		transform.invert()
		transform.concat()


# windows ####################################################################

# presenter window
presenter_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_screen_(
	PRESENTER_FRAME,
	NSMiniaturizableWindowMask|NSResizableWindowMask|NSTitledWindowMask,
	NSBackingStoreBuffered,
	NO,
	None,
)
presenter_window.setTitle_(name)
presenter_window.center()
presenter_window.makeKeyAndOrderFront_(nil)

presenter_view = PresenterView.alloc().initWithFrame_(presenter_window.frame())
presenter_window.setContentView_(presenter_view)
presenter_window.setInitialFirstResponder_(presenter_view)
presenter_window.makeFirstResponder_(presenter_view)


# presentation window
presentation_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_screen_(
	PRESENTER_FRAME,
	NSMiniaturizableWindowMask|NSResizableWindowMask|NSTitledWindowMask,
	NSBackingStoreBuffered,
	NO,
	None,
)
presentation_window.setTitle_(name)
presentation_window.makeKeyAndOrderFront_(nil)

presentation_view = NSView.alloc().initWithFrame_(presentation_window.frame())

slide_view = SlideView.alloc().initWithFrame_(presentation_view.frame())
web_view = WebView.alloc().initWithFrame_frameName_groupName_(presentation_view.frame(), nil, nil)

for view in [slide_view, web_view]:
	view.setAutoresizingMask_(NSViewWidthSizable|NSViewHeightSizable)
	view.setFrameOrigin_((0, 0))
	presentation_view.addSubview_(view)

def toggle_web_view(visible=None):
	if visible is None:
		visible = web_view.isHidden()
	web_view.setHidden_(not visible)
toggle_web_view(False)

presentation_window.setContentView_(presentation_view)
presentation_window.setInitialFirstResponder_(presentation_view)


# redisplay
redisplay_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
	1.,
	redisplayer, "display:",
	nil, YES)


# main loop ##################################################################

sys.exit(app.run())
